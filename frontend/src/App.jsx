import PasteLinkForm from "./PasteLinkForm.jsx";
import { checkLink } from "./scan.js";

export default function App({ check = checkLink }) {
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
