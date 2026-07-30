"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  content: string;
  variant?: "assistant" | "user";
};

export function MarkdownMessage({ content, variant = "assistant" }: Props) {
  if (variant === "user") {
    return <p className="whitespace-pre-wrap leading-relaxed">{content}</p>;
  }

  return (
    <div className="markdown-body text-sm leading-relaxed text-[var(--ink)]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="mb-2 mt-3 text-lg font-semibold first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-2 mt-3 text-base font-semibold first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-1.5 mt-2 text-sm font-semibold first:mt-0">{children}</h3>,
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
          ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
          li: ({ children }) => <li className="leading-snug">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          em: ({ children }) => <em className="italic text-[var(--muted)]">{children}</em>,
          a: ({ href, children }) => (
            <a href={href} className="underline decoration-[var(--accent)] underline-offset-2" target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-black/30 px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="mb-2 overflow-x-auto rounded-lg bg-black/35 p-3 font-mono text-xs last:mb-0">{children}</pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-l-2 border-[var(--accent)] pl-3 text-[var(--muted)] last:mb-0">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-[var(--line)]" />,
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="border border-[var(--line)] bg-black/20 px-2 py-1">{children}</th>,
          td: ({ children }) => <td className="border border-[var(--line)] px-2 py-1">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
