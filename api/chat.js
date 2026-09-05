import Anthropic from "@anthropic-ai/sdk";

// Edge runtime: streams the reply back token-by-token so the phone shows
// text as it is written instead of waiting for the whole response.
export const config = { runtime: "edge" };

const MODEL = "claude-opus-5";
const MAX_TOKENS = 8192;
const MAX_TURNS = 24; // keep the request small; older turns are dropped

const PERSONA = `You are Christian's personal assistant, speaking to him through his life dashboard.

You wrote the briefing he is looking at — the one included below. Talk like the person who wrote it: direct, warm, concrete. You know his situation, so don't ask him to re-explain it.

How to reply:
- He is almost always on his phone. Keep replies short — a few sentences. No headers, no bullet lists unless he asks for a list.
- Lead with the answer. Supporting detail after, only if it changes what he'd do.
- When he asks "what should I do", give him one thing, not a menu.
- Use the real numbers from the briefing below. Never invent a figure, date, or fact that isn't there — if you don't have it, say so plainly and say what would get it.
- You can't take actions yet — no paying bills, sending messages, or editing his dashboard. If he asks for one, say plainly that you can't do it from here yet, and give him the fastest way to do it himself.
- If he tells you something new (a decision, a race he picked, something he finished), acknowledge it and say it'll be in the next briefing. His replies here don't yet write back to the dashboard data.`;

function jsonLine(obj) {
  return new TextEncoder().encode(JSON.stringify(obj) + "\n");
}

async function loadContext(origin) {
  const grab = async (path) => {
    try {
      const res = await fetch(`${origin}/${path}`, { cache: "no-store" });
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  };
  const [briefing, data, whoop, plan, czech] = await Promise.all([
    grab("briefing.json"),
    grab("data.json"),
    grab("whoop-data.json"),
    grab("plan.json"),
    grab("czech.json"),
  ]);
  return { briefing, data, whoop, plan, czech };
}

function buildSystem({ briefing, data, whoop, plan, czech }) {
  const now = new Date().toLocaleString("en-AU", {
    timeZone: "Australia/Brisbane",
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

  const parts = [PERSONA, `\nRight now it is ${now} in Brisbane, where he lives.`];

  if (briefing) {
    parts.push(
      `\n--- TODAY'S BRIEFING (written ${briefing.writtenAt}) ---\n` +
        `${briefing.message.join("\n\n")}\n\n` +
        `Today's list: ${briefing.today.map((t) => `${t.text} [${t.level}]`).join(" | ")}\n` +
        `Numbers: ${briefing.numbers.map((n) => `${n.label} ${n.value}${n.note ? ` (${n.note})` : ""}`).join(" | ")}\n` +
        `On the radar: ${briefing.radar.join(" | ")}`
    );
  }

  if (data) {
    parts.push(
      `\n--- UNDERLYING DATA (last refreshed ${data.meta?.updatedAt}) ---\n` +
        `Sources wired up: ${data.meta?.sources}\n` +
        `Money: ${JSON.stringify(data.money)}\n` +
        `Pillar scores: ${data.pillars?.map((p) => `${p.name} ${p.score}/100 (${p.status})`).join(", ")}\n` +
        `Training plan: ${JSON.stringify(data.marathon)}`
    );
  }

  if (plan) {
    const start = new Date(`${plan.startDate}T00:00:00+10:00`);
    const day = Math.floor((Date.now() - start) / 86400000) + 1;
    parts.push(
      `\n--- THE CONTENT PLAN (day ${day} of 150) ---\n` +
        `This is the build he has given almost all his time to. It is now deliberately simple: one video a day, one Czech lesson a day. When he asks what to film, what to post, ` +
        `or what's next, answer from this — it is the plan, not a suggestion.\n` +
        JSON.stringify(plan)
    );
  }

  if (czech) {
    const start = new Date(`${czech.startDate}T00:00:00+10:00`);
    const d = Math.floor((Date.now() - start) / 86400000) + 1;
    const lesson = czech.lessons.find((l) => l.day === d);
    parts.push(
      `\n--- CZECH, DAY ${d} OF ${czech.blockDays} ---\n` +
        `He does one lesson a day in the dashboard. If he asks about Czech, quiz him, ` +
        `correct him, or explain something, work from the course — don't invent a different syllabus. ` +
        `Only use vocabulary and grammar he has already met (day ${d} and earlier) unless he asks to go ahead.\n` +
        (lesson ? `Today's lesson: ${JSON.stringify(lesson)}\n` : "") +
        `Whole course: ${JSON.stringify(czech.lessons.map((l) => ({ day: l.day, title: l.title, words: l.words.map((w) => w.c) })))}`
    );
  }

  if (whoop?.synced_at) {
    const ageDays = (Date.now() - new Date(whoop.synced_at)) / 86400000;
    parts.push(
      `\n--- WHOOP (synced ${whoop.synced_at}, ${ageDays.toFixed(0)} days ago${ageDays > 2 ? " — STALE, do not present these as today's numbers" : ""}) ---\n` +
        JSON.stringify({ recovery: whoop.recovery, sleep: whoop.sleep, strain: whoop.strain })
    );
  }

  return parts.join("\n");
}

export default async function handler(req) {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  // Optional shared passcode. Set CHAT_PASSCODE in Vercel to stop strangers
  // spending your API credit; leave it unset and the endpoint is open.
  const passcode = process.env.CHAT_PASSCODE;
  if (passcode && req.headers.get("x-dashboard-passcode") !== passcode) {
    return new Response(JSON.stringify({ error: "passcode" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }

  // No API key set. That's a supported mode, not an error: the page hands the
  // question to Claude with today's context attached, which runs on the user's
  // subscription instead of billing tokens.
  if (!process.env.ANTHROPIC_API_KEY) {
    return new Response(JSON.stringify({ handoff: true }), {
      status: 200,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Bad request" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  const messages = (Array.isArray(body.messages) ? body.messages : [])
    .filter((m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content.trim())
    .slice(-MAX_TURNS)
    .map((m) => ({ role: m.role, content: m.content.slice(0, 8000) }));

  if (!messages.length || messages[messages.length - 1].role !== "user") {
    return new Response(JSON.stringify({ error: "Nothing to send" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  const context = await loadContext(new URL(req.url).origin);
  const system = [
    { type: "text", text: buildSystem(context), cache_control: { type: "ephemeral" } },
  ];

  const base = {
    model: MODEL,
    max_tokens: MAX_TOKENS,
    // Adaptive thinking is on by default on Opus 5; low effort keeps replies
    // quick, which is what a phone check-in needs.
    output_config: { effort: "low" },
    system,
    messages,
  };

  const readable = new ReadableStream({
    async start(controller) {
      let emitted = false;

      const run = async (params, useBeta) => {
        const stream = useBeta
          ? client.beta.messages.stream({
              ...params,
              betas: ["server-side-fallback-2026-07-01"],
              fallbacks: "default",
            })
          : client.messages.stream(params);

        for await (const event of stream) {
          if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
            emitted = true;
            controller.enqueue(jsonLine({ t: event.delta.text }));
          }
        }

        const final = await stream.finalMessage();
        if (final.stop_reason === "refusal") {
          controller.enqueue(
            jsonLine({ error: "I can't answer that one — try asking it a different way." })
          );
        }
      };

      try {
        // Server-side fallback keeps a refused request working by re-running it
        // on another model. If the beta isn't available on this key, fall back
        // to a plain call — but only while nothing has been streamed yet.
        try {
          await run(base, true);
        } catch (err) {
          if (emitted) throw err;
          await run(base, false);
        }
      } catch (err) {
        const msg = err?.status === 401
          ? "The API key Vercel is using was rejected."
          : err?.status === 429
          ? "Rate limited — give it a minute and try again."
          : `Something broke reaching Claude: ${err?.message || err}`;
        controller.enqueue(jsonLine({ error: msg }));
      } finally {
        controller.close();
      }
    },
  });

  return new Response(readable, {
    headers: {
      "content-type": "application/x-ndjson; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
