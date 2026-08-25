// PHISHGUARD DASHBOARD APP SCRIPT

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const userSelector = document.getElementById("user-selector");
    const currentUserName = document.getElementById("current-user-name");
    const overallScorePercent = document.getElementById("overall-score-percent");
    const awarenessRating = document.getElementById("awareness-rating");
    const overallScoreCircle = document.getElementById("overall-score-circle");
    
    // Risk Card
    const riskBadge = document.getElementById("risk-badge");
    const riskText = document.getElementById("risk-text");
    const riskPointer = document.getElementById("risk-pointer");
    
    // Learning Stats
    const modulesCompletedText = document.getElementById("modules-completed-text");
    const modulesProgressFill = document.getElementById("modules-progress-fill");
    const videosCompletedText = document.getElementById("videos-completed-text");
    const videosProgressFill = document.getElementById("videos-progress-fill");
    const videoQuizAvgText = document.getElementById("video-quiz-avg-text");
    
    // Detailed sections
    const categoryBarsContainer = document.getElementById("category-bars-container");
    const strengthsList = document.getElementById("strengths-list");
    const weakAreasList = document.getElementById("weak-areas-list");
    const safetyTipsContainer = document.getElementById("safety-tips-container");
    const downloadPdfBtn = document.getElementById("download-pdf-btn");
    
    // Chart Instance Holder
    let performanceChart = null;
    
    // SVG circular progress settings (r=50, circumference is 2 * PI * r = ~314)
    const CIRCUMFERENCE = 314;
    overallScoreCircle.style.strokeDasharray = CIRCUMFERENCE;
    overallScoreCircle.style.strokeDashoffset = CIRCUMFERENCE;
    
    // Initialize Dashboard: Load Users List first
    fetchUsersList();
    
    function fetchUsersList() {
        fetch("/api/users")
            .then(res => res.json())
            .then(users => {
                userSelector.innerHTML = "";
                users.forEach(user => {
                    const option = document.createElement("option");
                    option.value = user.id;
                    option.textContent = `${user.anonymous_id} (${user.name})`;
                    userSelector.appendChild(option);
                });
                
                // Add event listener for user selection
                userSelector.addEventListener("change", (e) => {
                    if (e.target.value) {
                        loadUserReport(e.target.value);
                    }
                });
                
                // Load the first user by default
                if (users.length > 0) {
                    loadUserReport(users[0].id);
                }
            })
            .catch(err => {
                console.error("Error loading user profiles:", err);
                userSelector.innerHTML = '<option value="">Error loading profiles</option>';
            });
    }
    
    function loadUserReport(userId) {
        // Fetch specific user stats
        fetch(`/api/report-data/${userId}`)
            .then(res => res.json())
            .then(data => {
                updateDashboardUI(data);
            })
            .catch(err => {
                console.error(`Error loading report for user ${userId}:`, err);
            });
    }
    
    function updateDashboardUI(data) {
        // 1. Update Profile Information
        currentUserName.textContent = data.name;
        downloadPdfBtn.href = `/download-pdf/${data.user_id}`;
        
        // 2. Update Overall Score Circular Progress
        const percent = data.overall_percentage;
        overallScorePercent.textContent = `${percent}%`;
        awarenessRating.textContent = data.awareness_level;
        
        // SVG offset animation
        const offset = CIRCUMFERENCE - (percent / 100) * CIRCUMFERENCE;
        overallScoreCircle.style.strokeDashoffset = offset;
        
        // Change circle color depending on score
        if (percent >= 80) {
            overallScoreCircle.style.stroke = "#22c55e"; // Green
        } else if (percent >= 50) {
            overallScoreCircle.style.stroke = "#eab308"; // Yellow
        } else {
            overallScoreCircle.style.stroke = "#ef4444"; // Red
        }
        
        // 3. Update Risk Level Card
        riskText.textContent = `${data.risk_level} Risk`;
        
        // Reset classes
        riskBadge.className = "risk-badge";
        if (data.risk_level.toLowerCase() === "low") {
            riskBadge.classList.add("low");
            riskPointer.style.left = "15%";
        } else if (data.risk_level.toLowerCase() === "medium") {
            riskBadge.classList.add("med");
            riskPointer.style.left = "50%";
        } else {
            riskBadge.classList.add("high");
            riskPointer.style.left = "85%";
        }
        
        // 4. Update Learning Activity Details
        const lp = data.learning_progress;
        modulesCompletedText.textContent = `${lp.completed_modules}/${lp.total_modules}`;
        const modPercent = (lp.completed_modules / lp.total_modules) * 100;
        modulesProgressFill.style.width = `${modPercent}%`;
        
        videosCompletedText.textContent = `${lp.completed_videos}/${lp.total_videos}`;
        const vidPercent = (lp.completed_videos / lp.total_videos) * 100;
        videosProgressFill.style.width = `${vidPercent}%`;
        
        videoQuizAvgText.textContent = lp.video_quiz_avg > 0 ? `${lp.video_quiz_avg}%` : "N/A";
        
        // 5. Update Detailed Category Progress Bars
        renderCategoryBars(data.category_scores);
        
        // 6. Render Chart.js Chart
        renderRadarChart(data.category_scores);
        
        // 7. Update Strengths & Weak Areas Lists
        renderStrengthsAndWeaknesses(data.strengths, data.weak_areas);
        
        // 8. Update Personalized Security Tips
        renderSafetyTips(data.safety_tips);
    }
    
    // Map category tags to visual icons
    const iconMap = {
        "phishing": "fa-envelope-open-text",
        "password_security": "fa-key",
        "malware": "fa-bug",
        "social_engineering": "fa-people-arrows",
        "otp_scams": "fa-mobile-screen-button",
        "suspicious_links": "fa-link"
    };
    
    function renderCategoryBars(categories) {
        categoryBarsContainer.innerHTML = "";
        
        categories.forEach(cat => {
            const icon = iconMap[cat.category] || "fa-shield-halved";
            let scoreClass = "low-score";
            if (cat.percent >= 80) {
                scoreClass = "high-score";
            } else if (cat.percent >= 50) {
                scoreClass = "med-score";
            }
            
            const barHTML = `
                <div class="cat-bar-item">
                    <div class="cat-bar-meta">
                        <div class="cat-name-box">
                            <span class="cat-icon-badge"><i class="fa-solid ${icon}"></i></span>
                            <span>${cat.name}</span>
                        </div>
                        <span class="cat-percentage">${cat.percent}%</span>
                    </div>
                    <div class="cat-bar-track">
                        <div class="cat-bar-fill ${scoreClass}" style="width: ${cat.percent}%;"></div>
                    </div>
                </div>
            `;
            categoryBarsContainer.insertAdjacentHTML("beforeend", barHTML);
        });
    }
    
    function renderRadarChart(categories) {
        const labels = categories.map(c => c.name);
        const scores = categories.map(c => c.percent);
        
        const ctx = document.getElementById("performanceChart").getContext("2d");
        
        // Destroy existing chart instance to prevent duplicates
        if (performanceChart) {
            performanceChart.destroy();
        }
        
        // Dark theme parameters for Chart.js
        performanceChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Score (%)',
                    data: scores,
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    borderColor: '#3b82f6',
                    pointBackgroundColor: '#3b82f6',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#3b82f6',
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        grid: {
                            color: '#334155'
                        },
                        angleLines: {
                            color: '#334155'
                        },
                        pointLabels: {
                            color: '#cbd5e1',
                            font: {
                                family: "'Plus Jakarta Sans', sans-serif",
                                size: 10,
                                weight: 600
                            }
                        },
                        ticks: {
                            color: '#64748b',
                            backdropColor: 'transparent',
                            showLabelBackdrop: false,
                            stepSize: 20
                        },
                        suggestedMin: 0,
                        suggestedMax: 100
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    function renderStrengthsAndWeaknesses(strengths, weakAreas) {
        strengthsList.innerHTML = "";
        weakAreasList.innerHTML = "";
        
        if (strengths.length === 0) {
            strengthsList.innerHTML = '<li>No strong metrics identified yet. Keep learning!</li>';
        } else {
            strengths.forEach(s => {
                const li = document.createElement("li");
                li.innerHTML = `
                    <span>${s.name}</span>
                    <span class="insight-val-badge">${s.percent}%</span>
                `;
                strengthsList.appendChild(li);
            });
        }
        
        if (weakAreas.length === 0) {
            weakAreasList.innerHTML = '<li>Outstanding! No weak sectors detected.</li>';
        } else {
            weakAreas.forEach(w => {
                const li = document.createElement("li");
                const label = w.attempted ? `${w.percent}%` : "No Attempt";
                li.innerHTML = `
                    <span>${w.name}</span>
                    <span class="insight-val-badge">${label}</span>
                `;
                weakAreasList.appendChild(li);
            });
        }
    }
    
    // Tips mapping details for icon and header decoration
    const tipsStyleMap = {
        "Verify the sender's email": { icon: "fa-envelope-open-text", title: "Phishing Shield" },
        "Create strong, unique": { icon: "fa-key", title: "Password Fortress" },
        "Keep your system and antivirus": { icon: "fa-bug", title: "Malware Deflect" },
        "Be skeptical of unsolicited": { icon: "fa-people-arrows", title: "Human Defense" },
        "Never share One-Time": { icon: "fa-mobile-screen-button", title: "Credential Guard" },
        "Verify links by hovering": { icon: "fa-link", title: "Link Validator" },
        "Excellent job! Continue": { icon: "fa-shield-halved", title: "Active Hygiene" },
        "Maintain high vigilance": { icon: "fa-wifi", title: "Network Safe" }
    };
    
    function renderSafetyTips(tips) {
        safetyTipsContainer.innerHTML = "";
        
        tips.forEach(tip => {
            // Find appropriate icon style
            let icon = "fa-shield-halved";
            let title = "Defense Strategy";
            
            for (const key in tipsStyleMap) {
                if (tip.startsWith(key) || tip.includes(key)) {
                    icon = tipsStyleMap[key].icon;
                    title = tipsStyleMap[key].title;
                    break;
                }
            }
            
            const tipHTML = `
                <div class="tip-card">
                    <div class="tip-icon-box">
                        <i class="fa-solid ${icon}"></i>
                    </div>
                    <div class="tip-content">
                        <h4>${title}</h4>
                        <p>${tip}</p>
                    </div>
                </div>
            `;
            safetyTipsContainer.insertAdjacentHTML("beforeend", tipHTML);
        });
    }
});
