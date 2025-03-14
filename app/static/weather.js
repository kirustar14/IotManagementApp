document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("weather-form");
    const input = document.getElementById("city");
    const info = document.querySelector(".info");

    // Make sure the form is available
    if (!form || !input || !info) {
        console.error("Form or input elements are missing!");
        return;
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault(); // Prevent default form submission

        const city = input.value.trim();
        if (!city) {
            alert("Please enter a city name.");
            return;
        }

        try {
            // Step 1: Get the city coordinates (latitude and longitude) from OpenStreetMap's Nominatim API
            const locationResponse = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(city)}&format=json`);
            const locationData = await locationResponse.json();

            if (locationData.length === 0) {
                throw new Error("City not found.");
            }

            const lat = locationData[0].lat;
            const lon = locationData[0].lon;

            // Step 2: Use the coordinates to fetch the weather data from the National Weather Service API
            const weatherResponse = await fetch(`https://api.weather.gov/points/${lat},${lon}`);
            const weatherData = await weatherResponse.json();

            const forecastUrl = weatherData.properties.forecast;
            const forecastResponse = await fetch(forecastUrl);
            const forecastData = await forecastResponse.json();

            // Step 3: Extract relevant weather information
            const weather = forecastData.properties.periods[0]; // Get the first forecast period
            const locationText = `Location: ${city}`;
            const conditionText = `Condition: ${weather.shortForecast}`;
            const tempText = `Temperature: ${weather.temperature}°F`;

            // Step 5: Update the HTML with weather information
            info.innerHTML = `
                <p><strong>${locationText}</strong></p>
                <p>${conditionText}</p>
                <p>${tempText}</p>
            `;
        } catch (error) {
            console.error("Error fetching weather data:", error);
        }
    });

}); 


// Handle "What Should I Wear" button click
async function getOutfitSuggestion(temperature) {
    try {
        document.getElementById("ai-response").innerText = "Fetching outfit recommendation...";
        const response = await fetch("http://localhost:8000/get-outfit", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ temperature: temperature })
        });

        const data = await response.json();
        document.getElementById("ai-response").innerText = data.response || "No recommendation available.";
    } catch (error) {
        console.error("Error fetching AI response:", error);
        document.getElementById("ai-response").innerText = "Failed to get outfit recommendation.";
    }
} 