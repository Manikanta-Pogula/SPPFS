// static/js/login.js
document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("loginForm");
  const msg = document.getElementById("message");
  const btn = document.getElementById("submitBtn");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    msg.textContent = "";
    btn.disabled = true;
    btn.textContent = "Signing in...";

    const username = document.getElementById("username").value || "";
    const password = document.getElementById("password").value || "";

    // Build x-www-form-urlencoded body like a standard HTML form
    const formBody = new URLSearchParams();
    formBody.append("username", username);
    formBody.append("password", password);

    try {
      const resp = await fetch("/login", {
        method: "POST",
        credentials: "include", // crucial: accept and send session cookie
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formBody.toString(),
        redirect: "follow"
      });

      // Many Flask apps redirect on successful login. A 200/302 is fine.
      if (resp.ok || resp.status === 302) {
        // Success — redirect to SPA root
        window.location.href = "/";
      } else if (resp.status === 401) {
        msg.textContent = "Invalid credentials. Please try again.";
      } else {
        msg.textContent = `Login failed: ${resp.status} ${resp.statusText}`;
      }
    } catch (err) {
      console.error("Network/login error:", err);
      msg.textContent = "Network error — see console.";
    } finally {
      btn.disabled = false;
      btn.textContent = "Login";
    }
  });
});
