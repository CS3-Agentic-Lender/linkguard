import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import Missing from "./DoesNotExist.jsx"; // deliberate build error, removed before review
import "./styles/tokens.css";
import "./styles/app.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
