export function LongValue({
  value,
  path = false,
  nowrap = false,
}: {
  value?: string | null;
  path?: boolean;
  nowrap?: boolean;
}) {
  const text = value || "Not available";
  return (
    <span
      className={`block min-w-0 leading-6 ${
        nowrap ? "whitespace-nowrap" : "break-words"
      } ${path ? "[overflow-wrap:anywhere]" : ""
      }`}
      title={text}
    >
      {text}
    </span>
  );
}
