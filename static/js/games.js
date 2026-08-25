// PHISHGUARD GAMES CENTER SCRIPT

let activeUserId = null;
let currentTab = 'dashboard';

// Game Play State
let activeGameName = null;
let currentQuestions = [];
let currentQuestionIndex = 0;
let userAnswers = {}; // Map of question_id -> string (for radio) or array (for checkboxes)
let timerInterval = null;
let secondsElapsed = 0;

document.addEventListener("DOMContentLoaded", () => {
    // 1. Sync User Selector
    fetchUsersList();
    
    // Add change listener to selector
    const selector = document.getElementById("user-selector");
    selector.addEventListener("change", (e) => {
        if (e.target.value) {
            activeUserId = e.target.value;
            // Sync user avatar tag
            const selectedText = selector.options[selector.selectedIndex].text;
            const userName = selectedText.split("(")[1].replace(")", "");
            document.getElementById("current-user-name").textContent = userName;
            
            // Reload user progress stats
            loadUserGamification();
            if (currentTab === 'overall') {
                loadOverallReport();
            }
        }
    });
});

// Switch between dashboard, gamification, and overall report tabs
function switchTab(tabId) {
    currentTab = tabId;
    
    // Reset tabs UI
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));
    
    document.getElementById(`tab-${tabId}`).classList.add("active");
    document.getElementById(`content-${tabId}`).classList.add("active");
    
    // Hide active gameplay or reports when switching tabs
    document.getElementById("play-container-view").style.display = "none";
    document.getElementById("report-container-view").style.display = "none";
    document.querySelector(".games-nav-tabs").style.display = "flex";
    
    if (tabId === 'overall') {
        loadOverallReport();
    } else if (tabId === 'dashboard' || tabId === 'gamification') {
        loadUserGamification();
    }
}

// Fetch list of users for dropdown
function fetchUsersList() {
    fetch("/api/users")
        .then(res => res.json())
        .then(users => {
            const selector = document.getElementById("user-selector");
            selector.innerHTML = "";
            users.forEach(user => {
                const option = document.createElement("option");
                option.value = user.id;
                option.textContent = `${user.anonymous_id} (${user.name})`;
                selector.appendChild(option);
            });
            
            if (users.length > 0) {
                selector.value = users[0].id;
                activeUserId = users[0].id;
                document.getElementById("current-user-name").textContent = users[0].name;
                loadUserGamification();
            }
        })
        .catch(err => {
            console.error("Error loading user profiles:", err);
        });
}

// Load gamification data (XP, Levels, Badges)
function loadUserGamification() {
    if (!activeUserId) return;
    
    fetch(`/api/gamification-data/${activeUserId}`)
        .then(res => res.json())
        .then(data => {
            // Update Dashboard Progress Widgets
            document.getElementById("dash-level-number").textContent = data.level_num;
            document.getElementById("dash-level-title").textContent = data.level_name;
            document.getElementById("dash-points-value").textContent = data.points;
            
            if (data.level_num >= 5) {
                document.getElementById("dash-points-next").textContent = "Max Level Achieved";
                document.getElementById("dash-points-bar-fill").style.width = "100%";
            } else {
                document.getElementById("dash-points-next").textContent = `Next level at ${data.level_num * 300} XP`;
                document.getElementById("dash-points-bar-fill").style.width = `${data.progress_percent}%`;
            }
            
            // Update status badges on Game Cards
            const ldStatus = document.getElementById("ld-status-text");
            const srStatus = document.getElementById("sr-status-text");
            
            if (data.completed_games.includes("link_detective")) {
                ldStatus.textContent = "Completed";
                ldStatus.className = "status-badge status-completed";
            } else {
                ldStatus.textContent = "Not Attempted";
                ldStatus.className = "status-badge status-not-attempted";
            }
            
            if (data.completed_games.includes("scam_response")) {
                srStatus.textContent = "Completed";
                srStatus.className = "status-badge status-completed";
            } else {
                srStatus.textContent = "Not Attempted";
                srStatus.className = "status-badge status-not-attempted";
            }
            
            // Render dashboard mini badges row
            const dashBadgesRow = document.getElementById("dash-badges-row");
            dashBadgesRow.innerHTML = "";
            const earnedBadges = data.badges.filter(b => b.earned);
            if (earnedBadges.length === 0) {
                dashBadgesRow.innerHTML = '<span class="text-slate text-xs">Complete investigations to unlock badges</span>';
            } else {
                earnedBadges.forEach(badge => {
                    const badgeSpan = document.createElement("span");
                    badgeSpan.className = "badge-pill-mini";
                    badgeSpan.title = badge.desc;
                    badgeSpan.innerHTML = `${badge.icon} ${badge.name}`;
                    dashBadgesRow.appendChild(badgeSpan);
                });
            }
            
            // Update Gamification Tab Profile Details
            document.getElementById("profile-level-number").textContent = data.level_num;
            document.getElementById("profile-level-title").textContent = data.level_name;
            document.getElementById("profile-total-points").textContent = data.points;
            
            if (data.level_num >= 5) {
                document.getElementById("profile-points-label").textContent = `${data.points} XP (Level 5)`;
                document.getElementById("profile-points-bar-fill").style.width = "100%";
            } else {
                const levelCap = data.level_num * 300;
                const levelMin = (data.level_num - 1) * 300;
                document.getElementById("profile-points-label").textContent = `${data.level_progress} / ${data.next_level_points} XP`;
                document.getElementById("profile-points-bar-fill").style.width = `${data.progress_percent}%`;
            }
            
            // Render all badges with locked/unlocked visual statuses
            const badgesGrid = document.getElementById("profile-badges-grid");
            badgesGrid.innerHTML = "";
            data.badges.forEach(badge => {
                const badgeHTML = `
                    <div class="badge-item-card ${badge.earned ? 'unlocked' : 'locked'}">
                        <div class="badge-icon-wrap">${badge.icon}</div>
                        <h4>${badge.name}</h4>
                        <p>${badge.desc}</p>
                        <span class="badge-status-tag">${badge.earned ? '🟢 Earned' : '🔒 Locked'}</span>
                    </div>
                `;
                badgesGrid.insertAdjacentHTML("beforeend", badgeHTML);
            });
        })
        .catch(err => {
            console.error("Error loading gamification data:", err);
        });
}

// Load and render combined overall report
function loadOverallReport() {
    if (!activeUserId) return;
    
    const container = document.getElementById("overall-report-widget");
    container.innerHTML = '<div class="skeleton-loader"></div>';
    
    fetch(`/api/overall-report/${activeUserId}`)
        .then(res => res.json())
        .then(data => {
            let badgesEarnedHTML = "";
            if (data.badges.length === 0) {
                badgesEarnedHTML = "<p class='text-slate text-sm'>No badges earned yet. Attempt games to start unlocking achievements.</p>";
            } else {
                data.badges.forEach(badge => {
                    badgesEarnedHTML += `
                        <div class="report-badge-widget" title="${badge.desc}">
                            <span class="badge-icon">${badge.icon}</span>
                            <div class="badge-info">
                                <span class="badge-title">${badge.name}</span>
                                <span class="badge-xp">+30 XP</span>
                            </div>
                        </div>
                    `;
                });
            }
            
            let strengthsHTML = "";
            data.strengths.forEach(s => {
                strengthsHTML += `<li><i class="fa-solid fa-circle-check text-success"></i> <span>${s}</span></li>`;
            });
            
            let weaknessesHTML = "";
            data.weak_areas.forEach(w => {
                weaknessesHTML += `<li><i class="fa-solid fa-circle-xmark text-danger"></i> <span>${w}</span></li>`;
            });
            
            let safetyTipsHTML = "";
            data.safety_tips.forEach(tip => {
                safetyTipsHTML += `
                    <div class="safety-tip-bullet">
                        <i class="fa-solid fa-lightbulb text-warning"></i>
                        <p>${tip}</p>
                    </div>
                `;
            });
            
            let recModulesHTML = "";
            data.recommended_modules.forEach(mod => {
                recModulesHTML += `<span class="rec-module-pill"><i class="fa-solid fa-graduation-cap"></i> ${mod}</span>`;
            });
            
            // Cert button logic
            let certButtonHTML = "";
            if (data.certificate_unlocked) {
                certButtonHTML = `
                    <div class="cert-unlocked-card">
                        <div class="card-info">
                            <i class="fa-solid fa-award cert-icon-unlocked text-warning"></i>
                            <div>
                                <h3>Certificate Unlocked!</h3>
                                <p>Congratulations! You have demonstrated verified security awareness and are eligible to download your credentials.</p>
                            </div>
                        </div>
                        <a href="/download-certificate/${data.user_id}" class="btn btn-warning download-cert-btn">
                            <i class="fa-solid fa-file-pdf"></i> Generate & Download Certificate
                        </a>
                    </div>
                `;
            } else {
                certButtonHTML = `
                    <div class="cert-locked-card">
                        <div class="card-info">
                            <i class="fa-solid fa-lock cert-icon-locked text-slate"></i>
                            <div>
                                <h3>Certificate Locked</h3>
                                <p>To unlock your Certificate of Cybersecurity Awareness, you must complete both the <b>Link Detective Game</b> and the <b>Scam Response Challenge</b>.</p>
                            </div>
                        </div>
                        <button class="btn btn-secondary" disabled>
                            <i class="fa-solid fa-ban"></i> Complete Required Games
                        </button>
                    </div>
                `;
            }
            
            const riskClass = data.risk_level.toLowerCase();
            
            container.innerHTML = `
                <div class="overall-metrics-grid">
                    <div class="metric-card">
                        <h3>Games Completed</h3>
                        <p class="huge-value">${data.total_games_completed} / 2</p>
                    </div>
                    <div class="metric-card">
                        <h3>Overall Accuracy</h3>
                        <p class="huge-value">${data.overall_percentage}%</p>
                        <span class="sub-label">Grade: <b>${data.grade}</b> (${data.awareness_level})</span>
                    </div>
                    <div class="metric-card">
                        <h3>Current Risk Profile</h3>
                        <div class="risk-profile-badge ${riskClass}">
                            <span>${data.risk_level} Risk</span>
                        </div>
                        <span class="sub-label">Derived from game evaluations</span>
                    </div>
                </div>

                <div class="report-details-split">
                    <!-- Column 1: Strengths/Weaknesses/Tips -->
                    <div class="report-split-card">
                        <div class="insights-row">
                            <div class="insight-col">
                                <h4 class="text-success"><i class="fa-solid fa-circle-check"></i> Strengths</h4>
                                <ul class="insight-list">${strengthsHTML}</ul>
                            </div>
                            <div class="insight-col">
                                <h4 class="text-danger"><i class="fa-solid fa-circle-xmark"></i> Weaknesses</h4>
                                <ul class="insight-list">${weaknessesHTML}</ul>
                            </div>
                        </div>
                        
                        <div class="tips-box-widget">
                            <h4>Personalized Security Tips</h4>
                            <div class="tips-list-bullets">${safetyTipsHTML}</div>
                        </div>

                        <div class="rec-modules-widget">
                            <h4>Recommended Learning Modules</h4>
                            <div class="rec-modules-row">${recModulesHTML}</div>
                        </div>
                    </div>

                    <!-- Column 2: Badges & Certificates -->
                    <div class="report-split-card side-badges-cert">
                        <div class="earned-badges-report">
                            <h4>Earned Achievements</h4>
                            <div class="badges-row-flex">${badgesEarnedHTML}</div>
                        </div>
                        
                        ${certButtonHTML}
                    </div>
                </div>
            `;
        })
        .catch(err => {
            console.error("Error loading overall report:", err);
            container.innerHTML = '<p class="text-danger">Error loading report details. Please retry.</p>';
        });
}

// Start playing selected game
function startPlayGame(gameName) {
    if (!activeUserId) {
        alert("Please select a demo user profile first.");
        return;
    }
    
    activeGameName = gameName;
    userAnswers = {};
    secondsElapsed = 0;
    currentQuestionIndex = 0;
    
    // Hide navigation tabs and normal contents
    document.querySelector(".games-nav-tabs").style.display = "none";
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));
    document.getElementById("report-container-view").style.display = "none";
    
    // Load config
    fetch(`/api/game-config/${gameName}`)
        .then(res => res.json())
        .then(config => {
            currentQuestions = config;
            
            // Show play view
            document.getElementById("play-container-view").style.display = "block";
            
            // Populate titles
            document.getElementById("play-game-title").textContent = gameName === 'link_detective' ? 'Link Detective Game' : 'Scam Response Challenge';
            document.getElementById("play-game-subtitle").textContent = gameName === 'link_detective' ? 'Difficulty: Medium' : 'Difficulty: Hard';
            document.getElementById("play-total-questions").textContent = config.length;
            
            // Reset and start timer
            clearInterval(timerInterval);
            document.getElementById("timer-val").textContent = "00:00";
            timerInterval = setInterval(() => {
                secondsElapsed++;
                const mins = String(Math.floor(secondsElapsed / 60)).padStart(2, '0');
                const secs = String(secondsElapsed % 60).padStart(2, '0');
                document.getElementById("timer-val").textContent = `${mins}:${secs}`;
            }, 1000);
            
            // Render Left Side Navigation Grid
            renderQuestionNavGrid();
            
            // Load First Question
            loadQuestion(0);
        })
        .catch(err => {
            console.error("Error fetching game config:", err);
            exitGamePlay();
        });
}

// Exit the game play view
function exitGamePlay() {
    clearInterval(timerInterval);
    activeGameName = null;
    currentQuestions = [];
    userAnswers = {};
    
    document.getElementById("play-container-view").style.display = "none";
    document.getElementById("report-container-view").style.display = "none";
    
    // Restore tabs and tab content
    document.querySelector(".games-nav-tabs").style.display = "flex";
    switchTab('dashboard');
}

// Render Left Question Sidebar Navigation Grid
function renderQuestionNavGrid() {
    const grid = document.getElementById("play-nav-grid");
    grid.innerHTML = "";
    
    currentQuestions.forEach((q, idx) => {
        const item = document.createElement("button");
        item.className = "q-nav-item";
        item.id = `q-nav-${idx}`;
        item.textContent = idx + 1;
        item.onclick = () => loadQuestion(idx);
        grid.appendChild(item);
    });
}

// Load a specific question on the play board
function loadQuestion(index) {
    // Save current selection before moving
    saveCurrentSelection();
    
    currentQuestionIndex = index;
    const q = currentQuestions[index];
    
    // Update active nav item
    document.querySelectorAll(".q-nav-item").forEach((btn, i) => {
        btn.classList.remove("active");
        if (userAnswers[currentQuestions[i].id] !== undefined) {
            btn.classList.add("answered");
        } else {
            btn.classList.remove("answered");
        }
    });
    document.getElementById(`q-nav-${index}`).classList.add("active");
    
    // Set question content
    document.getElementById("play-current-index").textContent = index + 1;
    document.getElementById("play-scenario-text").textContent = q.scenario;
    
    // Render options
    const optionsContainer = document.getElementById("play-options-list");
    optionsContainer.innerHTML = "";
    
    const isMulti = activeGameName === 'scam_response';
    
    q.options.forEach(opt => {
        let isChecked = false;
        const currentAnswer = userAnswers[q.id];
        
        if (currentAnswer !== undefined) {
            if (isMulti) {
                isChecked = currentAnswer.includes(opt.id);
            } else {
                isChecked = currentAnswer === opt.id;
            }
        }
        
        const optionHTML = `
            <label class="option-label-wrapper ${isChecked ? 'selected' : ''}">
                <input type="${isMulti ? 'checkbox' : 'radio'}" name="question_option" value="${opt.id}" ${isChecked ? 'checked' : ''} onchange="toggleOptionHighlight(this)">
                <span class="option-marker">${opt.id}</span>
                <span class="option-text">${opt.text}</span>
            </label>
        `;
        optionsContainer.insertAdjacentHTML("beforeend", optionHTML);
    });
    
    // Update Action Buttons
    document.getElementById("play-prev-btn").style.visibility = index === 0 ? "hidden" : "visible";
    
    if (index === currentQuestions.length - 1) {
        document.getElementById("play-next-btn").style.display = "none";
        document.getElementById("play-submit-btn").style.display = "inline-flex";
    } else {
        document.getElementById("play-next-btn").style.display = "inline-flex";
        document.getElementById("play-submit-btn").style.display = "none";
    }
}

// Toggle option highlight on check
function toggleOptionHighlight(input) {
    const isMulti = activeGameName === 'scam_response';
    if (!isMulti) {
        // Clear highlights for siblings
        document.querySelectorAll(".option-label-wrapper").forEach(wrap => wrap.classList.remove("selected"));
    }
    
    if (input.checked) {
        input.parentElement.classList.add("selected");
    } else {
        input.parentElement.classList.remove("selected");
    }
}

// Save selections of current question index
function saveCurrentSelection() {
    if (currentQuestions.length === 0) return;
    const currentQ = currentQuestions[currentQuestionIndex];
    const inputs = document.getElementsByName("question_option");
    
    const isMulti = activeGameName === 'scam_response';
    
    if (isMulti) {
        const selections = [];
        inputs.forEach(input => {
            if (input.checked) selections.push(input.value);
        });
        if (selections.length > 0) {
            userAnswers[currentQ.id] = selections;
        }
    } else {
        let selection = null;
        inputs.forEach(input => {
            if (input.checked) selection = input.value;
        });
        if (selection !== null) {
            userAnswers[currentQ.id] = selection;
        }
    }
}

// Navigate questions
function navQuestion(direction) {
    const nextIdx = currentQuestionIndex + direction;
    if (nextIdx >= 0 && nextIdx < currentQuestions.length) {
        loadQuestion(nextIdx);
    }
}

// Submit answers to Flask Backend
function submitGameAnswers() {
    // Save last question state
    saveCurrentSelection();
    
    // Check if all questions are answered
    const unansweredCount = currentQuestions.filter(q => userAnswers[q.id] === undefined).length;
    if (unansweredCount > 0) {
        if (!confirm(`You have ${unansweredCount} unanswered questions. Do you still want to submit?`)) {
            return;
        }
    }
    
    // Stop Timer
    clearInterval(timerInterval);
    
    const payload = {
        user_id: activeUserId,
        game_name: activeGameName,
        answers: userAnswers,
        time_taken: secondsElapsed
    };
    
    // POST request
    fetch("/api/submit-game", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        renderIndividualReport(data);
    })
    .catch(err => {
        console.error("Error submitting game:", err);
        alert("There was an error saving your results. Please try again.");
    });
}

// Render individual report card after game submission
function renderIndividualReport(data) {
    // Hide gameplay panel
    document.getElementById("play-container-view").style.display = "none";
    // Show report panel
    document.getElementById("report-container-view").style.display = "block";
    
    // Reset feedback form
    document.getElementById("feedback-form").style.display = "block";
    document.getElementById("feedback-success-msg").style.display = "none";
    document.getElementById("feedback-form").reset();
    document.getElementById("feedback-session-id").value = data.session_id;
    
    // Populate score details
    const riskClass = data.risk_level.toLowerCase();
    const elapsedMins = String(Math.floor(data.time_taken / 60)).padStart(2, '0');
    const elapsedSecs = String(data.time_taken % 60).padStart(2, '0');
    
    const summaryBlock = document.getElementById("report-summary-block");
    summaryBlock.innerHTML = `
        <div class="summary-metric">
            <h3>Grade Issued</h3>
            <span class="report-grade-display">${data.grade}</span>
            <span class="text-slate font-semibold text-xs">${data.awareness_level} Awareness</span>
        </div>
        <div class="summary-metric">
            <h3>Simulation Score</h3>
            <span class="report-score-display">${data.score} / ${data.max_score}</span>
            <span class="text-slate font-semibold text-xs">Accuracy: ${data.percentage.toFixed(0)}%</span>
        </div>
        <div class="summary-metric">
            <h3>Time Taken</h3>
            <span class="report-time-display">${elapsedMins}:${elapsedSecs}</span>
            <span class="text-slate font-semibold text-xs">Elapsed Duration</span>
        </div>
        <div class="summary-metric">
            <h3>Vulnerability Risk</h3>
            <div class="risk-badge ${riskClass}">${data.risk_level} Risk</div>
        </div>
    `;
    
    // Render detailed answer review evidence
    const answersList = document.getElementById("report-answers-list");
    answersList.innerHTML = "";
    
    const isMulti = activeGameName === 'scam_response' || data.results[0].correct instanceof Array;
    
    data.results.forEach((res, idx) => {
        let yourChoiceText = "";
        let correctChoiceText = "";
        
        if (res.selected === null || res.selected === undefined) {
            yourChoiceText = "No Attempt";
        } else if (res.selected instanceof Array) {
            yourChoiceText = res.selected.join(", ");
        } else {
            yourChoiceText = res.selected;
        }
        
        if (res.correct instanceof Array) {
            correctChoiceText = res.correct.join(", ");
        } else {
            correctChoiceText = res.correct;
        }
        
        // Generate options listing HTML with descriptions
        let optionsListHTML = "";
        res.options.forEach(opt => {
            const letter = opt.id;
            const explanation = res.feedback[letter] || "No explanation provided.";
            const isCorrectOption = res.correct instanceof Array ? res.correct.includes(letter) : res.correct === letter;
            
            optionsListHTML += `
                <div class="evidence-opt-item ${isCorrectOption ? 'correct-opt' : 'wrong-opt'}">
                    <span class="opt-bullet">${letter}</span>
                    <div class="opt-desc-block">
                        <span class="opt-text-val"><b>${opt.text}</b></span>
                        <span class="opt-explanation">${explanation}</span>
                    </div>
                </div>
            `;
        });
        
        const cardHTML = `
            <div class="evidence-card ${res.is_correct ? 'correct' : 'wrong'}">
                <div class="evidence-card-header">
                    <span class="ev-index">Case Review #${idx + 1}: ${res.indicator}</span>
                    <span class="ev-result-badge ${res.is_correct ? 'correct' : 'wrong'}">
                        ${res.is_correct ? '✅ Correct' : '❌ Incorrect'}
                    </span>
                </div>
                <div class="evidence-card-body">
                    <p class="ev-scenario"><b>Investigation Scenario:</b> ${res.scenario}</p>
                    
                    <div class="user-choices-review">
                        <div>
                            <span>Your Choice:</span>
                            <strong class="${res.is_correct ? 'text-success' : 'text-danger'}">${yourChoiceText}</strong>
                        </div>
                        <div>
                            <span>Correct Action:</span>
                            <strong class="text-success">${correctChoiceText}</strong>
                        </div>
                    </div>

                    <div class="options-analysis-block">
                        <h4>Full Option Analysis & Feedback:</h4>
                        <div class="analysis-list-items">
                            ${optionsListHTML}
                        </div>
                    </div>

                    <div class="concept-corner">
                        <h4>🛡️ Cybersecurity Concept:</h4>
                        <p>${res.concept}</p>
                    </div>
                </div>
            </div>
        `;
        answersList.insertAdjacentHTML("beforeend", cardHTML);
    });
}

// Submit feedback form data
function submitFeedbackForm(event) {
    event.preventDefault();
    
    const sessionId = document.getElementById("feedback-session-id").value;
    const ratingInputs = document.getElementsByName("rating");
    let ratingVal = null;
    ratingInputs.forEach(input => {
        if (input.checked) ratingVal = input.value;
    });
    
    const payload = {
        session_id: sessionId,
        rating: ratingVal,
        liked_aspects: document.getElementById("liked_aspects").value,
        explanation_useful: document.getElementById("explanation_useful").value,
        difficulty: document.getElementById("difficulty").value,
        suggestions: document.getElementById("suggestions").value,
        comments: document.getElementById("comments").value
    };
    
    fetch("/api/submit-feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("feedback-form").style.display = "none";
        document.getElementById("feedback-success-msg").style.display = "block";
        // Refresh XP bar since they might get points or it refreshes session
        loadUserGamification();
    })
    .catch(err => {
        console.error("Error submitting feedback:", err);
        alert("Failed to submit feedback. Please try again.");
    });
}
