// Wording is copied word for word from the paste-a-link story.
export const PLACEHOLDER = "Checking isn't switched on yet, so we can't give a result for this link.";
export const CANT_CHECK = "We couldn't check that link just now. Please try again.";

/**
 * The backend turned the pasted text down (status 400). `message` is the
 * backend's own wording, such as "Paste a link first", shown next to the box.
 */
export class LinkError extends Error {}

/**
 * Sends the pasted text to the backend's POST /scan and resolves with its
 * reply, for the result card to show. This is the only request the page makes:
 * the link itself is never opened, fetched or previewed.
 *
 * Rejects with a LinkError when the backend says what's wrong with the pasted
 * text. Rejects with a plain Error when the backend can't be reached or replies
 * with any other error, so the form shows its "couldn't check" message rather
 * than a blank screen. A reply the card can't read, such as a level it doesn't
 * know or a body that isn't an object, still reaches the card, which shows the
 * same message for it rather than a guess.
 */
export async function checkLink(link, fetchImpl = fetch) {
  const response = await fetchImpl("/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: link }),
  });
  if (response.status === 400) {
    const reply = await response.json().catch(() => ({}));
    if (typeof reply.error === "string" && reply.error.trim()) {
      throw new LinkError(reply.error);
    }
  }
  if (!response.ok) {
    throw new Error(`/scan replied with status ${response.status}.`);
  }

  const reply = await response.json();
  // A body such as null, 0 or a list carries no level, so it gets the card's failure message.
  return reply !== null && typeof reply === "object" && !Array.isArray(reply) ? reply : {};
}
