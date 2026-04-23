import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";

const token = window.location.pathname.split("/")[2] ?? "";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App token={token} />
  </StrictMode>
);
