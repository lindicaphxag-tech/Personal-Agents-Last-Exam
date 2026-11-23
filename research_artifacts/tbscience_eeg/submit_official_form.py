"""Official TB-Science public Airtable preapproval submission.

Runs only when expressly requested by Zhibo Zhang; never bypasses challenge.
Checks all required fields and accepts success only from Airtable page after Submit.
"""
from __future__ import annotations
import sys
import time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

FORM = "https://airtable.com/appzZC5gEHrXSfNNw/pagjgS95lAQ5FVJxt/form"
DATA = {
    "Name": "Zhibo Zhang",
    "Email": "lindicaphxag@gmail.com",
    "Affiliation": "Hangzhou Dianzi University, Hangzhou, China",
    "Role": "Undergraduate Researcher in Artificial Intelligence (EEG / scientific computing)",
    "GitHub Name": "lindicaphxag-tech",
    "Professional Profile": "https://github.com/lindicaphxag-tech",
    "Academic Profile": "https://orcid.org/0009-0007-3533-1941",
    "Relevant Experience": (
        "I conduct EEG and scientific-computing research on reference conventions, robust channel reconstruction "
        "and reproducibility. My merged contributions to Braindecode include exact reverse-bipolar "
        "derivation handling (PR #1577) and channel-name normalization (PR #1597), and I contributed "
        "to MOABB's integer-only PurgedEpochKFold (PR #1329). Braindecode v2.1.0 formally "
        "lists me as a released software author. For this task I implemented and tested a "
        "CPU-only, synthetic, identifiability-aware EEG inverse-reconstruction pilot."
    ),
    "Relevant Academic Work": (
        "Verified research-software work in this task domain: "
        "https://github.com/braindecode/braindecode/pull/1577 ; "
        "https://github.com/braindecode/braindecode/pull/1597 ; "
        "https://github.com/NeuroTechX/moabb/pull/1329 ; "
        "https://github.com/braindecode/braindecode/blob/v2.1.0/CITATION.cff . "
        "These links document peer-reviewed open-source code contributions and a released "
        "software authorship, not authorship of the original Braindecode or MOABB journal papers. "
        "The author can supply additional verified bibliographic details on request."
    ),
    "Proposal Title": (
        "Identifiability-Aware Reconstruction of Heterogeneous Bipolar EEG Montages "
        "Under Correlated Noise and Saturation"
    ),
    "Subfield": "Neuroscience / EEG signal processing; measurement-graph inverse problems",
    "Scientific Problem": (
        "EEG laboratories routinely encounter recordings assembled under heterogeneous bipolar "
        "references, polarity and unit conventions, and partially redundant electrode graphs. "
        "Observed differences do not identify absolute electrode potentials. When components are "
        "disconnected, each has an independent reference gauge; an isolated bridge lead lacks the "
        "independent cycle evidence required to infer a flipped sign. Amplifier saturation and "
        "correlated noise can make otherwise identifiable channels unreliable. The proposed "
        "scientific workflow recovers only supported bipolar contrasts, reports structural "
        "non-identifiability explicitly, and prevents calibration/evaluation leakage. This "
        "problem comes from practical EEG montage work and related released Braindecode changes; "
        "the current benchmark pilot uses synthetic mechanistic recordings, not patients."
    ),
    "Workflow Details": (
        "Inputs: 42 synthetic multi-session EEG recordings with electrode and signed lead metadata, "
        "time series, disjoint read-only noise calibration records, manifest hashes and a documented "
        "output schema. Some recording graphs contain redundant cycles; others have disconnected "
        "components, reversed or duplicated leads, correlated errors and saturation bursts. "
        "Tasks: parse units/aliases; construct per-session directed incidence matrices; determine "
        "connected components and gauge freedom; detect only cycle-supported polarity errors; "
        "estimate robust noise weights from calibration data; reconstruct electrode-space signals "
        "with separate per-component gauges; identify unresolved contrasts. Outputs: reconstructed "
        "signals and predicted bipolar contrasts, accepted/reversed/ambiguous flags, rank and "
        "gauge report, and deterministic provenance. No hidden latent truth, private verifier or "
        "reference solution is agent-visible. Equivalent legitimate algorithms are accepted."
    ),
    "Requirements": (
        "Python 3.11 or newer, NumPy, SciPy and pytest; Linux and standard command-line tools. "
        "Proposed execution environment: 2-4 CPU cores, about 4-8 GB RAM, no GPU, less than 1 GB "
        "working storage. Existing 42-recording synthetic pilot and two reference methods run "
        "locally on CPU; we have not measured a standardized benchmark wall-clock time and do "
        "not claim a certified Harbor runtime. A containerized reference/oracle will be provided "
        "after scientific preapproval."
    ),
    "Dataset": (
        "Current pilot: 42 entirely synthetic recordings across six independently generated "
        "cohorts, containing 198 identifiable target waveforms. A deterministic NumPy generator "
        "creates structured electrode graphs, signed bipolar observations, calibrated "
        "correlated noise, sparse artifacts and saturation. Public-facing agent inputs are "
        "separated from hidden generator state, latent truth and scoring fixtures. The task "
        "does not require patient data or paid/proprietary datasets. Current detailed reviewer "
        "archive is not yet publicly downloadable; it can be shared with authorized auditors "
        "before a proposed upstream implementation. Dataset bytes are not yet independently "
        "measured."
    ),
    "Evaluation Strategy": (
        "A deterministic pytest verifier will check schema, manifest integrity, signed lead "
        "orientation decisions, rank and gauge constraints, finite numeric outputs, and "
        "gauge-invariant reconstruction errors on private reference signals. A frozen maximum "
        "NRMSE threshold of 0.12 was used in the local pilot; both the author's oracle "
        "(worst fresh-cohort max NRMSE 0.0444) and an independently structured "
        "median/GLS/low-pass reference solved all 6 fresh cohorts. A local CPU emulator passed "
        "32/32 independent contract tests and rejected no-op and malformed-output attacks. "
        "These are solvability and negative-control results, not official Harbor/Docker tests. "
        "Final tests will also penalize hallucinated signs on non-identifiable bridges and "
        "disallow fitting covariance or thresholds on held-out observations."
    ),
    "Complexity": (
        "Conceptually, this combines gauge-constrained graph inversion, multi-reference EEG "
        "semantics, correlated noise, robust reconstruction, and calibration leakage control. "
        "A researcher implementing and documenting the method from scratch would require "
        "substantially more work than running an existing solver, but that person-hour estimate "
        "has not been measured. Importantly, the current synthetic cohort is solved quickly "
        "by two independent CPU reference algorithms; thus frontier-agent difficulty HAS NOT "
        "been demonstrated. I request domain-science pre-review to assess genuine benchmark "
        "fit and whether an authentic additional research obstacle or real public data is "
        "needed before main-track implementation. I do not claim any tested frontier-model "
        "failure rates."
    ),
    "References & Resources": (
        "https://github.com/braindecode/braindecode/pull/1577 ; "
        "https://github.com/braindecode/braindecode/pull/1597 ; "
        "https://github.com/NeuroTechX/moabb/pull/1329 ; "
        "https://github.com/braindecode/braindecode/blob/v2.1.0/CITATION.cff ; "
        "https://github.com/harbor-framework/terminal-bench-science"
    ),
    "Additional Info": (
        "AI-assisted drafting, implementation, test scaffolding and scientific review are "
        "disclosed. This is an original candidate for review, not an approved task; two related "
        "EEG task ideas exist privately for other benchmarks and have not been submitted. "
        "I will not duplicate an exclusive task submission without reviewer permission. "
        "I am willing to maintain an accepted main-benchmark task and analyze agent failures, "
        "subject to direct project communication."
    ),
    "COI": (
        "Submitting as a university undergraduate researcher, not on behalf of an "
        "evaluation vendor or a commercial organization. I am not aware of any financial "
        "stake in the benchmark outcome or relationship to its reviewers. No patient or "
        "proprietary data are used. AI-assisted proposal preparation is disclosed above."
    ),
}

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome",headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
    page = browser.new_page(locale="en-US",viewport={"width":1450,"height":1000})
    seen=[]
    page.on("response",lambda r: seen.append((r.status,urlparse(r.url).netloc,urlparse(r.url).path[:110])) if r.request.method!="GET" else None)
    page.goto(FORM,wait_until="domcontentloaded",timeout=55000)
    page.wait_for_timeout(5500)
    title=page.title()
    print("FORM_TITLE",title)
    assert "Terminal-Bench-Science: Task Proposal Form" in title, "wrong form"
    try:
        page.get_by_role("button",name="Reject All, Except Strictly Necessary").click(timeout=1000)
    except Exception:
        pass
    ta=page.locator("textarea")
    print("TEXTAREA_COUNT",ta.count())
    assert ta.count()==11, "unexpected textarea count: refuse to mis-map"
    # All textareas appear in the same DOM order as the official form field sequence.
    fields=["Name","Email","Affiliation","Role","GitHub Name","Professional Profile","Academic Profile"]
    for i,f in enumerate(fields):
        ta.nth(i).fill(DATA[f]);print("FILL",f,"OK")
    # Structured experience fields use plaintext contenteditable elements.
    page.locator('[contenteditable="plaintext-only"][aria-label="Relevant Experience"]').fill(DATA["Relevant Experience"])
    page.locator('[contenteditable="plaintext-only"]').nth(1).fill(DATA["Relevant Academic Work"])
    ta.nth(8).fill(DATA["Proposal Title"])
    ta.nth(9).fill(DATA["Subfield"])
    print("FILL_BASIC_OK")
    # Select scientific domain and field using actual visible Airtable menu options.
    for index,value in [(0,"Life Sciences"),(1,"Neuroscience")]:
        combos=page.locator('[role="combobox"]')
        assert combos.count()==2,("combobox count",combos.count())
        combos.nth(index).click()
        page.wait_for_timeout(350)
        options=[x.inner_text().strip() for x in page.locator('[role="option"]').all() if x.is_visible()]
        print("CHOICES",index,repr(options[:35]))
        try:
            page.get_by_role("option",name=value,exact=True).first.click(timeout=2500)
        except Exception:
            page.get_by_text(value,exact=True).last.click(timeout=3500)
        print("SELECT",value,"OK")
    # Rich-text editors are aligned with the seven official question headings.
    editors=page.locator('.ql-editor[contenteditable="true"]')
    assert editors.count()==7, ("rich-editor count",editors.count())
    rich=["Scientific Problem","Workflow Details","Requirements","Dataset", "Evaluation Strategy", "Complexity", "References & Resources"]
    for i,f in enumerate(rich):
        editors.nth(i).fill(DATA[f])
        print("FILL_RICH",f,"OK")
    page.locator('[contenteditable="plaintext-only"][aria-label="COI"]').fill(DATA["COI"])
    page.locator('[contenteditable="plaintext-only"]').nth(2).fill(DATA["Additional Info"])
    invalid=page.locator('[aria-required="true"][aria-invalid="true"]')
    print("REQUIRED_INVALID_COUNT_BEFORE_SUBMIT",invalid.count())
    print("REQUIRED_INVALID_DETAILS",invalid.evaluate_all("els => els.map(x => ({tag:x.tagName,aria:x.getAttribute('aria-label'),label:x.getAttribute('aria-labelledby')}))"))
    assert invalid.count() == 0, "Refuse to submit an incomplete form"
    print("SUBMIT_READY",page.get_by_role("button",name="Submit",exact=True).is_enabled())
    # Explicit user authorization granted in current chat: submit exactly once.
    page.get_by_role("button",name="Submit",exact=True).click(timeout=15000)
    print("SUBMIT_CLICKED_ONCE")
    page.wait_for_timeout(7500)
    print("AFTER_URL",page.url)
    after=page.locator("body").inner_text(timeout=10000)
    print("AFTER_BODY",after[:5500])
    print("POST_RESPONSE_STATUSES",seen[-15:])
    success = any(t in after.lower() for t in ["thank you for submitting","your response has been submitted","your form has been submitted","form submitted successfully","your submission has been received","submission successful"])
    print("OFFICIAL_SUBMISSION_SUCCESS",success)
    if success:
        page.screenshot(path="tbscience-confirmation.png",full_page=True)
    browser.close()
    if not success:
        print("ERROR: No affirmative official confirmation; treat as NOT submitted")
        sys.exit(3)
