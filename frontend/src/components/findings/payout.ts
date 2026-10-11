/** Parse a dollar amount typed by the user into cents. Empty means "no payout". */
export function parsePayout(input: string): { cents: number | null; error: string | null } {
  const v = input.trim().replace(/^\$/, "");
  if (v === "") return { cents: null, error: null };
  if (!/^\d+(\.\d{1,2})?$/.test(v)) {
    return { cents: null, error: "Enter a dollar amount like 250 or 250.50." };
  }
  return { cents: Math.round(Number(v) * 100), error: null };
}

export function payoutToInput(cents: number | null): string {
  return cents == null ? "" : (cents / 100).toFixed(2);
}
