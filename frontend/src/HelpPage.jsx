import { HELP_LINK_TEXT, HELP_ROUTES } from "./advice.js";

export const HELP_INTRO = "If you think you've been sent a scam, these are the places in Ireland to report it or get help.";
export const BACK_TEXT = "Back to the link checker";

/**
 * The "Where to get help" page: the Irish reporting routes from docs/advice.md,
 * as a list a screen reader can step through. It holds no links out of the app,
 * only the way back to the checker.
 */
export default function HelpPage() {
  return (
    <section className="help-page" aria-labelledby="help-heading">
      <h1 id="help-heading" tabIndex={-1}>
        {HELP_LINK_TEXT}
      </h1>
      <p className="lead">{HELP_INTRO}</p>
      <ul className="help-page__routes">
        {HELP_ROUTES.map(({ situation, where }) => (
          <li key={situation}>
            <span className="help-page__situation">{situation}</span>
            <span className="help-page__where">{where}</span>
          </li>
        ))}
      </ul>
      <p>
        <a className="text-link" href="#">
          {BACK_TEXT}
        </a>
      </p>
    </section>
  );
}
