// Review portal page. Signs in with Cognito managed login (authorization code flow with PKCE),
// then claims review tasks and submits labels through the review API at /api/*.
// No third-party code: the page's Content-Security-Policy allows scripts from this site only.
"use strict";

const STORAGE_KEY = "reviewPortalSession";
const SIGN_IN_KEY = "reviewPortalSignIn";
let config;
let session = null;
let currentTask = null;

const $ = (id) => document.getElementById(id);

function show(sectionId) {
  for (const id of ["signed-out", "idle", "task"]) {
    $(id).hidden = id !== sectionId;
  }
}

function setStatus(message, isError = false) {
  $("status").textContent = message || "";
  $("status").classList.toggle("error", Boolean(isError));
}

function setBusy(busy) {
  for (const button of document.querySelectorAll("main button")) {
    button.disabled = busy;
  }
}

// PKCE and sign-in ----------------------------------------------------------------------------

function base64Url(bytes) {
  let text = "";
  for (const byte of new Uint8Array(bytes)) {
    text += String.fromCharCode(byte);
  }
  return btoa(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function randomString(byteCount) {
  return base64Url(crypto.getRandomValues(new Uint8Array(byteCount)));
}

async function signIn() {
  const verifier = randomString(48);
  const state = randomString(24);
  const challenge = base64Url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
  sessionStorage.setItem(SIGN_IN_KEY, JSON.stringify({ verifier, state }));
  const query = new URLSearchParams({
    response_type: "code",
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    scope: "openid email profile",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  window.location.assign(`${config.cognitoDomain}/oauth2/authorize?${query}`);
}

async function requestTokens(body) {
  const response = await fetch(`${config.cognitoDomain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: config.clientId, ...body }),
  });
  if (!response.ok) {
    throw new Error(`Cognito returned ${response.status}`);
  }
  return response.json();
}

function saveTokens(tokens, previousRefreshToken) {
  session = {
    accessToken: tokens.access_token,
    idToken: tokens.id_token,
    refreshToken: tokens.refresh_token || previousRefreshToken,
    expires: Date.now() + (tokens.expires_in - 60) * 1000,
  };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

async function finishSignIn(params) {
  const saved = JSON.parse(sessionStorage.getItem(SIGN_IN_KEY) || "null");
  sessionStorage.removeItem(SIGN_IN_KEY);
  window.history.replaceState(null, "", config.redirectUri);
  if (!saved || params.get("state") !== saved.state) {
    throw new Error("The sign-in response didn't match this browser tab. Sign in again.");
  }
  const tokens = await requestTokens({
    grant_type: "authorization_code",
    code: params.get("code"),
    redirect_uri: config.redirectUri,
    code_verifier: saved.verifier,
  });
  saveTokens(tokens);
}

async function refreshTokens() {
  if (!session || !session.refreshToken) {
    return false;
  }
  try {
    saveTokens(await requestTokens({ grant_type: "refresh_token", refresh_token: session.refreshToken }), session.refreshToken);
    return true;
  } catch {
    return false;
  }
}

async function signOut() {
  const refreshToken = session && session.refreshToken;
  session = null;
  sessionStorage.removeItem(STORAGE_KEY);
  if (refreshToken) {
    // Revoke the refresh token. Ignore errors, because sign-out continues anyway.
    await fetch(`${config.cognitoDomain}/oauth2/revoke`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ token: refreshToken, client_id: config.clientId }),
    }).catch(() => {});
  }
  const query = new URLSearchParams({ client_id: config.clientId, logout_uri: config.redirectUri });
  window.location.assign(`${config.cognitoDomain}/logout?${query}`);
}

function userName() {
  try {
    const payload = JSON.parse(atob(session.idToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.email || payload["cognito:username"] || "";
  } catch {
    return "";
  }
}

// Review API --------------------------------------------------------------------------------

class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function api(path, body, retried = false) {
  if (Date.now() >= session.expires && !(await refreshTokens())) {
    throw new ApiError(401, "SignedOut", "Your session ended. Sign in again.");
  }
  const response = await fetch(path, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.accessToken}`, "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (response.status === 401 && !retried && (await refreshTokens())) {
    return api(path, body, true);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, data.error || "Error", data.message || `The request failed (${response.status}).`);
  }
  return data;
}

function formatTime(isoTime) {
  return new Date(isoTime).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

async function claimTask() {
  setBusy(true);
  setStatus("Getting the next image…");
  try {
    const data = await api("/api/tasks/claim");
    currentTask = data.task;
    if (!currentTask) {
      setStatus("");
      $("idle-message").textContent = "No images are waiting for review. Check again later.";
      $("start").textContent = "Check again";
      show("idle");
      return;
    }
    showTask(currentTask, data.waiting);
    setStatus("");
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

function showTask(task, waiting) {
  const labels = $("labels");
  labels.replaceChildren();
  for (const label of task.labels) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (label === "None of the above") {
      button.classList.add("secondary");
    }
    button.addEventListener("click", () => submitLabel(label));
    labels.append(button);
  }
  $("image").src = task.imageUrl;
  $("claim-time").textContent = `This image is yours until ${formatTime(task.claimExpires)}.`;
  $("waiting").textContent = waiting === 1 ? "1 more image is waiting." : `${waiting} more images are waiting.`;
  show("task");
  labels.querySelector("button").focus();
}

async function submitLabel(label) {
  setBusy(true);
  setStatus(`Saving ${label}…`);
  try {
    await api(`/api/tasks/${encodeURIComponent(currentTask.id)}/submit`, { label });
    setStatus(`Saved ${label}.`);
    currentTask = null;
    await claimTask();
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

async function releaseTask() {
  setBusy(true);
  try {
    await api(`/api/tasks/${encodeURIComponent(currentTask.id)}/release`);
    currentTask = null;
    $("idle-message").textContent = "You gave the image back, so another reviewer can label it.";
    $("start").textContent = "Start reviewing";
    show("idle");
    setStatus("");
  } catch (error) {
    handleError(error);
  } finally {
    setBusy(false);
  }
}

function handleError(error) {
  if (error.status === 401) {
    session = null;
    sessionStorage.removeItem(STORAGE_KEY);
    show("signed-out");
    setStatus(error.message, true);
  } else if (error.status === 403) {
    show("idle");
    $("idle-message").textContent = "";
    setStatus(`${error.message} Ask an administrator to add you to the group.`, true);
  } else if (error.status === 409) {
    currentTask = null;
    show("idle");
    $("idle-message").textContent = "Choose Start reviewing to get the next image.";
    setStatus(`${error.message}`, true);
  } else {
    setStatus(error.message || "Something went wrong. Try again.", true);
  }
}

// Start -------------------------------------------------------------------------------------

async function start() {
  $("sign-in").addEventListener("click", signIn);
  $("sign-out").addEventListener("click", signOut);
  $("start").addEventListener("click", claimTask);
  $("release").addEventListener("click", releaseTask);
  // If the presigned image URL ran out before the image loaded, claim again to get a new URL.
  $("image").addEventListener("error", () => {
    if (currentTask) {
      claimTask();
    }
  });

  try {
    config = await (await fetch("config.json", { cache: "no-store" })).json();
    const params = new URLSearchParams(window.location.search);
    if (params.has("error")) {
      window.history.replaceState(null, "", config.redirectUri);
      throw new Error(params.get("error_description") || "Sign-in failed.");
    }
    if (params.has("code")) {
      await finishSignIn(params);
    } else {
      session = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
    }
  } catch (error) {
    setStatus(error.message, true);
  }

  if (!session) {
    show("signed-out");
    return;
  }
  $("user-name").textContent = userName();
  $("account").hidden = false;
  show("idle");
}

start();
