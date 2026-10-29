// Wording is copied word for word from the paste-a-link story.
export const PLACEHOLDER = "Checking isn't switched on yet, so we can't give a result for this link.";

/**
 * Sends the pasted text to the backend's POST /scan and resolves with the
 * message to show. This is the only request the page makes: the link itself
 * is never opened, fetched or previewed.
 *
 * Rejects when the backend can't be reached, replies with an error, or sends a
 * reply this page can't show yet, so the form shows its "couldn't check" message
 * rather than a blank screen or a guess.
 */
export async function checkLink(link, fetchImpl = fetch) {
  const response = await fetchImpl("/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: link }),
  });
  if (!response.ok) {
    throw new Error(`/scan replied with status ${response.status}.`);
  }

  const reply = await response.json();
  if (reply.placeholder === true) {
    return PLACEHOLDER;
  }
  // A real risk level belongs on the result card, which isn't built yet.
  throw new Error("/scan sent a result this page can't show yet.");
}
