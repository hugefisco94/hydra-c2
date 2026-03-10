const resultEl = document.getElementById("result");
const healthPill = document.getElementById("health-pill");
const form = document.getElementById("login-form");
const briefingPanel = document.getElementById("briefing-panel");
const briefingContent = document.getElementById("briefing-content");
const checklistForm = document.getElementById("checklist-form");
const checklistProgress = document.getElementById("checklist-progress");
const reportNotes = document.getElementById("report-notes");
const reportPreview = document.getElementById("report-preview");
const reportCopyButton = document.getElementById("report-copy");

let currentScenario = null;

async function loadPolicy() {
  const response = await fetch("/wargame/health");
  const body = await response.json();
  healthPill.textContent = body.briefing_only ? "briefing-only" : "unsafe";
  resultEl.textContent = JSON.stringify(body, null, 2);
}

function renderBriefing(data) {
  const scenario = data.scenario;
  currentScenario = scenario;
  const html = `
    <article class="brief-card">
      <p class="brief-classification">${scenario.classification}</p>
      <h3>${scenario.title}</h3>
      <p class="brief-summary">${scenario.summary}</p>
      <div class="brief-grid">
        <section>
          <h4>Objectives</h4>
          <ul>${scenario.objectives.map((item) => `<li>${item}</li>`).join("")}</ul>
        </section>
        <section>
          <h4>Watch Items</h4>
          <ul>${scenario.watch_items.map((item) => `<li>${item}</li>`).join("")}</ul>
        </section>
        <section>
          <h4>Permitted Actions</h4>
          <ul>${scenario.permitted_actions.map((item) => `<li>${item}</li>`).join("")}</ul>
        </section>
        <section>
          <h4>Blocked Actions</h4>
          <ul>${scenario.blocked_actions.map((item) => `<li>${item}</li>`).join("")}</ul>
        </section>
      </div>
    </article>
  `;

  briefingContent.innerHTML = html;
  renderChecklist(scenario);
  updateReportPreview();
  briefingPanel.hidden = false;
}

function renderChecklist(scenario) {
  checklistForm.innerHTML = scenario.checklist_items
    .map(
      (item, index) => `
        <label class="check-item">
          <input type="checkbox" name="check-${index}" />
          <span>${item}</span>
        </label>
      `,
    )
    .join("");

  checklistForm.querySelectorAll("input").forEach((input) => {
    input.addEventListener("change", updateChecklistProgress);
  });
  updateChecklistProgress();
}

function updateChecklistProgress() {
  const total = checklistForm.querySelectorAll('input[type="checkbox"]').length;
  const done = checklistForm.querySelectorAll('input[type="checkbox"]:checked').length;
  checklistProgress.textContent = `${done} / ${total}`;
  updateReportPreview();
}

function buildReportText() {
  if (!currentScenario) {
    return "Report preview will appear here.";
  }

  const checkedItems = Array.from(
    checklistForm.querySelectorAll('input[type="checkbox"]:checked'),
  ).map((input) => input.parentElement.textContent.trim());

  const noteText = reportNotes.value.trim() || "No analyst note recorded yet.";
  const sections = currentScenario.report_sections
    .map((section) => `- ${section}`)
    .join("\n");

  return [
    `Scenario: ${currentScenario.title}`,
    `Classification: ${currentScenario.classification}`,
    `Region: ${currentScenario.region}`,
    "",
    "Checklist Complete:",
    checkedItems.length > 0 ? checkedItems.map((item) => `- ${item}`).join("\n") : "- None yet",
    "",
    "Report Sections:",
    sections,
    "",
    "Analyst Notes:",
    noteText,
  ].join("\n");
}

function updateReportPreview() {
  reportPreview.textContent = buildReportText();
}

reportNotes.addEventListener("input", updateReportPreview);

reportCopyButton.addEventListener("click", async () => {
  const text = buildReportText();
  try {
    await navigator.clipboard.writeText(text);
    reportCopyButton.textContent = "Copied";
    window.setTimeout(() => {
      reportCopyButton.textContent = "Copy Summary";
    }, 1200);
  } catch (error) {
    reportCopyButton.textContent = "Copy Failed";
    window.setTimeout(() => {
      reportCopyButton.textContent = "Copy Summary";
    }, 1200);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const data = new FormData(form);
  const credentials = Object.fromEntries(data.entries());

  const response = await fetch("/wargame/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentials),
  });

  const body = await response.json();
  resultEl.textContent = JSON.stringify(body, null, 2);

  if (!response.ok || !body.session_token) {
    briefingPanel.hidden = true;
    briefingContent.innerHTML = "";
    checklistForm.innerHTML = "";
    checklistProgress.textContent = "0 / 0";
    reportNotes.value = "";
    currentScenario = null;
    updateReportPreview();
    return;
  }

  const briefingResponse = await fetch("/wargame/scenario/briefing", {
    headers: { "X-Demo-Session": body.session_token },
  });
  const briefing = await briefingResponse.json();
  resultEl.textContent = JSON.stringify({ auth: body, briefing }, null, 2);
  if (briefingResponse.ok) {
    renderBriefing(briefing);
  }
});

loadPolicy().catch((error) => {
  healthPill.textContent = "error";
  resultEl.textContent = `Startup error: ${error}`;
});
