window.onload = async function () {
    const temperatureData = await fetchData('temperature');

    // Create the charts with decimation enabled
    createChart('temperatureChart', temperatureData, 'Temperature Readings', 'Temperature');
};

// Fetch data from the API
async function fetchData(sensorType) {
    const response = await fetch(`http://localhost:8000/api/${sensorType}`);
    const data = await response.json();
    
    // For temperature, only include data from 2025 and plot every point
    if (sensorType === 'temperature') {
        const filteredData = data.filter(entry => {
            const entryDate = new Date(entry.timestamp);
            return entryDate >= new Date("2025-01-01T00:00:00");
        });
        return filteredData.map(entry => ({
            x: new Date(entry.timestamp),
            y: entry.value
        }));
    } 
}

// Create the chart for each sensor type
function createChart(chartId, data, chartTitle, label) {
    const ctx = document.getElementById(chartId).getContext('2d');

    // Add title above the chart
    const chartContainer = document.getElementById(chartId).parentElement;
    const titleElement = document.createElement('h3');
    titleElement.textContent = chartTitle;
    chartContainer.insertBefore(titleElement, chartContainer.firstChild);

    new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                label: label,
                data: data,
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                fill: false,
                pointRadius: 0 // Hides the data point markers
            }]
        },
        options: {
            plugins: {
                decimation: {
                    enabled: true,
                    algorithm: 'min-max', // Options: 'min-max', 'lttb'
                    threshold: 100 // Number of points after which decimation is triggered
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        tooltipFormat: 'll HH:mm'
                    },
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: label
                    }
                }
            }
        }
    });
}

// Handle "What Should I Wear" button click
async function getOutfitSuggestion() {
    try {
        // Show loading message
        document.getElementById("ai-response").innerText = "Fetching outfit recommendation...";

        // Make the API request
        const response = await fetch("http://localhost:8000/get-outfit", { 
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });

        // Parse response
        const data = await response.json();

        // Display the response from the AI
        document.getElementById("ai-response").innerText = data.response || "No recommendation available.";
    } catch (error) {
        console.error("Error fetching AI response:", error);
        document.getElementById("ai-response").innerText = "Failed to get outfit recommendation.";
    }
}

// Toggle chat visibility
function toggleChat() {
    const chatContainer = document.getElementById("chat-container");
    chatContainer.style.display = (chatContainer.style.display === "none" || chatContainer.style.display === "") ? "block" : "none";
}

// Send user message and get AI response
async function sendMessage() {
    const userMessage = document.getElementById("user-message").value;
    if (userMessage.trim() === "") return;

    // Display user message
    addMessage(userMessage, "user");

    // Clear input field
    document.getElementById("user-message").value = "";

    try {
        // Make API call to get AI response
        const response = await fetch("http://localhost:8000/get-chat-response", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: userMessage })
        });

        const data = await response.json();
        const aiMessage = data.response || "Sorry, I couldn't understand that.";

        // Display AI response
        addMessage(aiMessage, "ai");
    } catch (error) {
        console.error("Error fetching AI response:", error);
    }
}

// Add message to chat box
function addMessage(message, sender) {
    const chatBox = document.getElementById("chat-box");
    const messageBubble = document.createElement("div");
    messageBubble.classList.add("message-bubble");
    messageBubble.classList.add(sender === "user" ? "user-bubble" : "ai-bubble");
    messageBubble.textContent = message;
    chatBox.appendChild(messageBubble);
    chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to the latest message
}
