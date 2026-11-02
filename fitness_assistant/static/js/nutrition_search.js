// Live search and macro calculator for MSc Fitness Assistant

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('foodSearchInput');
    const searchSpinner = document.getElementById('searchSpinner');
    const searchResults = document.getElementById('searchResults');

    // Portion Modal elements
    const portionModal = document.getElementById('portionModal');
    const closeModalBtn = document.getElementById('closePortionModal');
    const modalFoodName = document.getElementById('modalFoodName');
    const modalMacroInfo = document.getElementById('modalMacroInfo');
    const portionInput = document.getElementById('modal_portion');

    // Hidden form inputs
    const hiddenFoodName = document.getElementById('hidden_food_name');
    const hiddenCalories = document.getElementById('hidden_calories');
    const hiddenProtein = document.getElementById('hidden_protein');
    const hiddenCarbs = document.getElementById('hidden_carbs');
    const hiddenFats = document.getElementById('hidden_fats');

    // Scaled text preview elements
    const scaledCals = document.getElementById('scaledCals');
    const scaledProtein = document.getElementById('scaledProtein');
    const scaledCarbs = document.getElementById('scaledCarbs');
    const scaledFats = document.getElementById('scaledFats');

    let debounceTimer;
    let selectedFood = null; // Holds the currently selected food's nutrients per 100g

    // Debounce wrapper
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const query = searchInput.value.trim();
        
        if (query.length < 2) {
            searchResults.innerHTML = '';
            searchResults.classList.add('hidden');
            return;
        }

        searchSpinner.classList.remove('hidden');

        debounceTimer = setTimeout(() => {
            fetch(`/nutrition/api/search/?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    renderSearchResults(data);
                })
                .catch(err => {
                    console.error('Error fetching food data:', err);
                    searchResults.innerHTML = `<div class="p-4 text-xs text-red-500 font-medium">Failed to search foods. Please try again.</div>`;
                })
                .finally(() => {
                    searchSpinner.classList.add('hidden');
                });
        }, 300);
    });

    // Render search results list
    function renderSearchResults(foods) {
        searchResults.innerHTML = '';
        if (!foods || foods.length === 0) {
            searchResults.innerHTML = `<div class="p-4 text-sm text-gray-500">No matching foods found.</div>`;
            searchResults.classList.remove('hidden');
            return;
        }

        foods.forEach(food => {
            const card = document.createElement('div');
            card.className = 'p-4 flex justify-between items-center cursor-pointer hover:bg-gray-100/80 transition duration-150';
            card.innerHTML = `
                <div>
                    <h5 class="text-sm font-semibold text-gray-950">${food.name}</h5>
                    <p class="text-xs text-gray-400 mt-0.5">
                        P: ${food.protein}g &bull; C: ${food.carbs}g &bull; F: ${food.fats}g (per 100g)
                    </p>
                </div>
                <div class="text-right">
                    <span class="text-sm font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg">${food.kcal_per_100g} kcal</span>
                </div>
            `;
            
            // Set up click handler to open selection modal
            card.addEventListener('click', () => {
                openModal(food);
            });

            searchResults.appendChild(card);
        });

        searchResults.classList.remove('hidden');
    }

    // Modal Operations
    function openModal(food) {
        selectedFood = food;
        modalFoodName.textContent = food.name;
        modalMacroInfo.textContent = `P: ${food.protein}g, C: ${food.carbs}g, F: ${food.fats}g`;
        
        // Fill hidden form fields
        hiddenFoodName.value = food.name;
        hiddenCalories.value = food.kcal_per_100g;
        hiddenProtein.value = food.protein;
        hiddenCarbs.value = food.carbs;
        hiddenFats.value = food.fats;

        // Reset portion input to default 100g and recalculate
        portionInput.value = 100;
        updateScaledPreviews();

        portionModal.classList.remove('hidden');
    }

    function closeModal() {
        portionModal.classList.add('hidden');
        selectedFood = null;
    }

    // Recalculate scaled macros on input change
    function updateScaledPreviews() {
        if (!selectedFood) return;
        const portion = parseFloat(portionInput.value) || 0;
        const scale = portion / 100;

        const calories = Math.round(selectedFood.kcal_per_100g * scale);
        const protein = (selectedFood.protein * scale).toFixed(1);
        const carbs = (selectedFood.carbs * scale).toFixed(1);
        const fats = (selectedFood.fats * scale).toFixed(1);

        scaledCals.textContent = calories;
        scaledProtein.textContent = `${protein}g`;
        scaledCarbs.textContent = `${carbs}g`;
        scaledFats.textContent = `${fats}g`;
    }

    portionInput.addEventListener('input', updateScaledPreviews);
    closeModalBtn.addEventListener('click', closeModal);

    // Close modal on background overlay click
    portionModal.addEventListener('click', (e) => {
        if (e.target === portionModal) {
            closeModal();
        }
    });
});
