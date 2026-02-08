/**
 * Final landing section: circle with Google icon for sign-in.
 */
import { useState } from "react";
import { useGoogleLogin } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export function GoogleSignInSection() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pseudoLoginSuccess, setPseudoLoginSuccess] = useState(false);

  // Pseudo login: Try to load token.json first
  const handlePseudoLogin = async () => {
    // Prevent OAuth if we're already processing pseudo login
    if (pseudoLoginSuccess) {
      console.log("✅ Pseudo login already successful, skipping");
      return;
    }
    setLoading(true);
    setError(null);
    
    try {
      console.log("🔍 Attempting pseudo login with token.json...");
      // Try to fetch token.json from public folder
      const response = await fetch("/token.json", {
        cache: "no-cache", // Ensure we get fresh token
      });
      
      console.log("📡 Fetch response status:", response.status, response.statusText);
      
      if (response.ok) {
        let tokenData;
        try {
          tokenData = await response.json();
        } catch (jsonError) {
          console.error("❌ Failed to parse token.json as JSON:", jsonError);
          throw new Error("Invalid JSON in token.json");
        }
        
        console.log("📦 Token data loaded:", { 
          hasToken: !!(tokenData.token || tokenData.access_token),
          expiry: tokenData.expiry,
          hasRefreshToken: !!tokenData.refresh_token,
          keys: Object.keys(tokenData)
        });
        
        // Extract access token (handle both formats)
        const accessToken = tokenData.token || tokenData.access_token;
        
        console.log("🔑 Access token extracted:", accessToken ? `${accessToken.substring(0, 20)}...` : "NOT FOUND");
        
        if (accessToken) {
          // Check if token is expired (but use it anyway for pseudo login)
          let expiresIn = 3600; // Default 1 hour
          
          if (tokenData.expiry) {
            const expiryDate = new Date(tokenData.expiry);
            const now = new Date();
            const secondsUntilExpiry = Math.floor((expiryDate.getTime() - now.getTime()) / 1000);
            console.log("⏰ Token expiry check:", {
              expiry: tokenData.expiry,
              now: now.toISOString(),
              secondsUntilExpiry
            });
            
            if (secondsUntilExpiry > 0) {
              expiresIn = secondsUntilExpiry;
            } else {
              console.warn("⚠️ Token in token.json has expired, but using it anyway for pseudo login");
              // Still use it for pseudo login even if expired
              expiresIn = 3600; // Set default expiry
            }
          } else if (tokenData.expires_in) {
            expiresIn = tokenData.expires_in;
          }
          
          console.log("✅ Using token from token.json for pseudo login");
          
          // Set user with token
          setUser({
            access_token: accessToken,
            expires_in: expiresIn,
          });
          
          // Send token to backend (non-blocking)
          fetch("/api/v1/auth/google-token", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              access_token: accessToken,
              expires_in: expiresIn,
            }),
          })
            .then(async (res) => {
              const data = await res.json();
              console.log("📤 Backend response:", data);
            })
            .catch((e) => {
              console.error("Failed to send token to backend:", e);
              // Continue anyway - user is authenticated
            });
          
          // IMPORTANT: Set flag and navigate immediately to prevent OAuth flow
          setPseudoLoginSuccess(true);
          setLoading(false);
          navigate("/dashboard", { replace: true });
          return; // This prevents login() from being called
        } else {
          console.warn("⚠️ token.json found but no access token in it");
        }
      } else {
        console.warn(`⚠️ Failed to fetch token.json: ${response.status} ${response.statusText}`);
        console.warn("💡 Make sure token.json exists in frontend/public/ folder");
      }
    } catch (err) {
      console.error("❌ Error loading token.json:", err);
      console.error("💡 Error details:", err instanceof Error ? err.message : String(err));
      // Fall through to normal OAuth flow
    }
    
    // Only call login() if we didn't successfully load token.json and haven't already succeeded
    if (!pseudoLoginSuccess) {
      setLoading(false);
      console.log("🔄 Token.json not available, falling back to OAuth flow");
      // If token.json doesn't work, use normal OAuth
      login();
    } else {
      setLoading(false);
    }
  };

  const login = useGoogleLogin({
    flow: "implicit",
    scope: "https://www.googleapis.com/auth/calendar.readonly",
    // redirect_uri is automatically set to window.location.origin by the library
    // Make sure Google Cloud Console has: http://localhost:3000 and http://localhost:8080
    onSuccess: async (tokenResponse) => {
      setError(null);
      setUser({
        access_token: tokenResponse.access_token,
        expires_in: tokenResponse.expires_in ?? 0,
      });
      
      // Send the token to the backend so it can use it for Calendar API
      try {
        await fetch("/api/v1/auth/google-token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            access_token: tokenResponse.access_token,
            expires_in: tokenResponse.expires_in,
          }),
        });
      } catch (e) {
        console.error("Failed to send token to backend:", e);
        // Continue anyway - user is authenticated
      }
      
      navigate("/dashboard", { replace: true });
    },
    onError: (errorResponse) => {
      console.error("Google OAuth error:", errorResponse);
      const errorCode = errorResponse.error;
      // Check error code as string to handle type safety
      const errorStr = errorCode ? String(errorCode) : "";
      if (errorStr === "invalid_client" || errorStr.includes("invalid_client")) {
        setError(
          "OAuth client not found. Please check:\n" +
          "1. VITE_GOOGLE_CLIENT_ID in frontend/.env matches Google Cloud Console\n" +
          "2. JavaScript origins added: http://localhost:3000, http://localhost:8080\n" +
          "3. Redirect URIs added: http://localhost:3000, http://localhost:8080"
        );
      } else {
        setError(`OAuth error: ${errorStr || "unknown"}. ${errorResponse.error_description || ""}`);
      }
    },
  });

  return (
    <section className="min-h-screen flex flex-col items-center justify-center bg-background px-4">
      <p className="text-muted-foreground text-sm mb-8">Sign in to continue</p>
      {error && (
        <div className="mb-4 max-w-md p-4 rounded-lg bg-red-500/10 border border-red-500/30">
          <p className="text-sm text-red-400">{error}</p>
          <p className="text-xs text-red-300/70 mt-2">
            Check: 1) VITE_GOOGLE_CLIENT_ID in frontend/.env 2) JavaScript origins in Google Cloud Console
          </p>
        </div>
      )}
      <button
        type="button"
        className="w-16 h-16 rounded-full flex items-center justify-center bg-background border-2 border-border hover:border-primary hover:bg-secondary transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Sign in with Google"
        onClick={handlePseudoLogin}
        disabled={loading}
      >
        {loading ? (
          <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        ) : (
          <GoogleIcon className="w-8 h-8 text-foreground" />
        )}
      </button>
    </section>
  );
}

/** Standard Google "G" logo SVG for sign-in button. */
function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}
