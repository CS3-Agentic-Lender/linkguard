import PasteLinkForm from "./PasteLinkForm.jsx";

// Sending the link to /scan is the wire-up subtask's job. Until it lands, a
// check can't reach the backend, so the page says so instead of guessing.
function notConnectedYet() {
  return Promise.reject(new Error("The page is not connected to /scan yet."));
}

export default function App({ check = notConnectedYet }) {
  return (
    <main className="page">
      <p className="logo">LinkGuard</p>
      <h1>Is this link safe?</h1>
      <p className="lead">
        Paste a link from a text, email or message. We check it for you without opening it.
      </p>
      <PasteLinkForm check={check} />
    </main>
  );
}
