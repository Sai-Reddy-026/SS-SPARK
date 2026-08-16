import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Fragment } from "react";
import { toast } from "sonner";

/** Minimal markdown renderer for headings, lists, bold/italic, inline & fenced code. */
function renderInline(text: string, keyPrefix: string) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean);
  return tokens.map((token, i) => {
    const key = `${keyPrefix}-${i}`;
    if (token.startsWith("`") && token.endsWith("`")) {
      return (
        <code
          key={key}
          className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.85em] text-foreground"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    if (token.startsWith("**") && token.endsWith("**")) {
      return (
        <strong key={key} className="font-semibold text-foreground">
          {token.slice(2, -2)}
        </strong>
      );
    }
    if (token.startsWith("*") && token.endsWith("*")) {
      return <em key={key}>{token.slice(1, -1)}</em>;
    }
    return <Fragment key={key}>{token}</Fragment>;
  });
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    void navigator.clipboard?.writeText(code).then(() => {
      setCopied(true);
      toast.success("Code copied!");
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="overflow-hidden rounded-xl border bg-muted/40 my-1">
      <div className="flex items-center justify-between border-b bg-muted/60 px-3 py-1.5">
        <span className="font-mono text-xs text-muted-foreground">{lang || "code"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
          aria-label="Copy code"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-green-500" />
              <span className="text-green-500">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 font-mono text-[0.82rem] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function Markdown({ content }: { content: string }) {
  const blocks = content.split(/```/);

  return (
    <div className="space-y-2 text-[0.95rem] leading-relaxed text-foreground/90">
      {blocks.map((block, blockIndex) => {
        if (blockIndex % 2 === 1) {
          const [rawLang, ...rest] = block.replace(/^\n/, "").split("\n");
          const maybeLang = rawLang ?? "";
          const isLang = /^[a-z]+$/i.test(maybeLang.trim());
          const code = (isLang ? rest.join("\n") : block.replace(/^\n/, "")).replace(/\n$/, "");
          return (
            <CodeBlock
              key={blockIndex}
              lang={isLang ? maybeLang.trim() : ""}
              code={code}
            />
          );
        }

        const lines = block.split("\n");
        return (
          <Fragment key={blockIndex}>
            {lines.map((line, lineIndex) => {
              const key = `${blockIndex}-${lineIndex}`;
              const trimmed = line.trim();
              if (!trimmed) return null;
              if (trimmed.startsWith("### ")) {
                return (
                  <h4 key={key} className="pt-1 text-sm font-semibold tracking-tight text-foreground">
                    {renderInline(trimmed.slice(4), key)}
                  </h4>
                );
              }
              if (trimmed.startsWith("## ")) {
                return (
                  <h3 key={key} className="pt-2 text-base font-semibold text-foreground">
                    {renderInline(trimmed.slice(3), key)}
                  </h3>
                );
              }
              if (trimmed.startsWith("# ")) {
                return (
                  <h2 key={key} className="pt-2 text-lg font-bold text-foreground">
                    {renderInline(trimmed.slice(2), key)}
                  </h2>
                );
              }
              const ordered = trimmed.match(/^(\d+)\.\s+(.*)$/);
              if (ordered) {
                return (
                  <div key={key} className="flex gap-2 pl-1">
                    <span className="mt-0.5 shrink-0 font-mono text-xs font-semibold text-primary">{ordered[1]}.</span>
                    <p>{renderInline(ordered[2] ?? "", key)}</p>
                  </div>
                );
              }
              if (trimmed.startsWith("- ")) {
                return (
                  <div key={key} className="flex gap-2 pl-1">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    <p>{renderInline(trimmed.slice(2), key)}</p>
                  </div>
                );
              }
              return <p key={key}>{renderInline(trimmed, key)}</p>;
            })}
          </Fragment>
        );
      })}
    </div>
  );
}
