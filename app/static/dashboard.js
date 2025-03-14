// Global chart variable
let chartInstance = null;

// Initial setup when page loads
window.onload = async function () {
    const initialTemperatureData = await fetchData('temperature');
    chartInstance = createChart('temperatureChart', initialTemperatureData, 'Temperature Readings', 'Temperature');
    switchTab('chat');

    // Set interval to fetch new data every second and update the chart
    setInterval(async () => {
        // console.log("updating plot");
        const newData = await fetchData('temperature'); // Fetch new data
        updateChart(chartInstance, newData); // Update the chart with new data
    }, 1000); // Update every second
};

// Fetch data from the API
async function fetchData(sensorType) {
    const response = await fetch(`https://iotmanagementapp.onrender.com/api/temperature`);
    const data = await response.json();
    
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

// Create or update the chart
function createChart(chartId, data, chartTitle, label) {
    const ctx = document.getElementById(chartId).getContext('2d');
    const chartContainer = document.getElementById(chartId).parentElement;
    const titleElement = document.createElement('h3');
    titleElement.textContent = chartTitle;
    chartContainer.insertBefore(titleElement, chartContainer.firstChild);

    return new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                label: label,
                data: data,
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                fill: false,
                pointRadius: 0
            }]
        },
        options: {
            plugins: {
                decimation: {
                    enabled: true,
                    algorithm: 'min-max',
                    threshold: 100
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

// Update the chart data
function updateChart(chartInstance, newData) {
    if (chartInstance) {
        // console.log("adding new data");
        chartInstance.data.datasets[0].data = newData; // Update chart data
        chartInstance.update(); // Re-render the chart
    }
}

// Switch between tabs
function switchTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Show the selected tab
    document.getElementById(tabName).classList.add('active');
}

// Handle sending chat messages
async function sendMessage() {
    const userMessage = document.getElementById("user-message").value;
    if (userMessage.trim() === "") return;

    addMessage(userMessage, "user");
    document.getElementById("user-message").value = "";

    try {
        const response = await fetch("https://iotmanagementapp.onrender.com/get-chat-response", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: userMessage })
        });

        const data = await response.json();
        addMessage(data.response || "Sorry, I couldn't understand that.", "ai");
    } catch (error) {
        console.error("Error sending message:", error);
        addMessage("Error. Please try again.", "ai");
    }
}

// Add a new message to the chat
function addMessage(message, sender) {
    const chatBox = document.getElementById("chat-box");
    const messageElement = document.createElement("div");
    messageElement.classList.add("message-bubble", sender === "user" ? "user-bubble" : "ai-bubble");
    messageElement.textContent = message;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Generate an image
async function generateImage() {
    const prompt = document.getElementById("image-prompt").value.trim();
    if (!prompt) {
        alert("Please enter a description for the image.");
        return;
    }

    try {
        document.getElementById("ai-response").innerText = "Generating image...";
        document.getElementById("ai-image").style.display = "none";

        const response = await fetch("https://iotmanagementapp.onrender.com/generate-image", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt })
        });

        const data = await response.json();

        if (data.image_url) {
            document.getElementById("ai-image").src = data.image_url;
        } else if (data.image_base64) {
            document.getElementById("ai-image").src = data.image_base64;
        } else {
            document.getElementById("ai-response").innerText = "Failed to generate image.";
            return;
        }

        document.getElementById("ai-image").style.display = "block";
        document.getElementById("ai-response").innerText = "";

    } catch (error) {
        console.error("Error generating image:", error);
        document.getElementById("ai-response").innerText = "Error occurred while generating image.";
    }
}
