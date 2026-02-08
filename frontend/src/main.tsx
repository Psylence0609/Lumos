import { GoogleOAuthProvider } from "@react-oauth/google";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import "./index.css";

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

// Warn if client ID is not configured
if (!clientId || clientId === "") {
  console.warn(
    "⚠️ VITE_GOOGLE_CLIENT_ID not set in .env file.\n" +
    "Create frontend/.env with: VITE_GOOGLE_CLIENT_ID=your_client_id_here\n\n" +
    "Google Cloud Console setup:\n" +
    "- JavaScript origins: http://localhost:3000, http://localhost:8080\n" +
    "- Redirect URIs: http://localhost:3000, http://localhost:8080"
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={clientId}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </GoogleOAuthProvider>
  </StrictMode>
);
