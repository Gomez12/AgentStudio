import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/catalog/skills")) {
          return Promise.resolve(
            new Response(JSON.stringify({ items: [{ slug: "writer", name: "writer", description: "Draft clear copy", tags: [], body: "Write clearly.", path: "/skills/writer/SKILL.md" }], issues: [] }))
          );
        }
        if (url.endsWith("/catalog/tools")) {
          return Promise.resolve(
            new Response(JSON.stringify({ items: [{ slug: "search_tool", name: "search", description: "Search", input_schema: {}, module_path: "/tools/search_tool.py", builder_name: "build_tool" }], issues: [] }))
          );
        }
        if (url.endsWith("/agents")) {
          return Promise.resolve(new Response(JSON.stringify([])));
        }
        if (url.endsWith("/runs")) {
          return Promise.resolve(new Response(JSON.stringify([])));
        }
        if (url.endsWith("/schedules")) {
          return Promise.resolve(new Response(JSON.stringify([])));
        }
        if (url.endsWith("/settings/llm")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                default_provider_id: "openai",
                default_model: "gpt-4.1-mini",
                providers: [
                  {
                    id: "openai",
                    label: "OpenAI",
                    endpoint_url: "https://api.openai.com/v1",
                    models: ["gpt-4.1-mini", "gpt-4.1"],
                  },
                ],
              })
            )
          );
        }
        return Promise.resolve(new Response(JSON.stringify([])));
      })
    );
  });

  it("renders the studio sections and loaded catalog data", async () => {
    render(<App />);

    expect(await screen.findByText("Agent Studio")).toBeInTheDocument();
    expect(await screen.findByText("Skill catalog")).toBeInTheDocument();
    expect((await screen.findAllByText("writer")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("search")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Agent builder")).toBeInTheDocument();
    expect(await screen.findByText("Run history")).toBeInTheDocument();
    expect(await screen.findByText("Provider registry")).toBeInTheDocument();
  });
});
