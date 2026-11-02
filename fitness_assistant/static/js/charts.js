// Chart rendering for MSc Fitness Assistant

document.addEventListener('DOMContentLoaded', () => {

    // --- 1. WORKOUT VOLUME CHART (Line Chart) ---
    const workoutChartCanvas = document.getElementById('workoutVolumeChart');
    if (workoutChartCanvas) {
        const chartDataElement = document.getElementById('chart-data');
        if (chartDataElement) {
            try {
                const chartData = JSON.parse(chartDataElement.textContent);
                
                // Extract labels (dates) and data points (volumes)
                const labels = chartData.map(item => item.date);
                const volumes = chartData.map(item => item.volume);

                new Chart(workoutChartCanvas, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Volume (kg)',
                            data: volumes,
                            borderColor: '#3b82f6', // brand blue
                            backgroundColor: 'rgba(59, 130, 246, 0.08)',
                            fill: true,
                            tension: 0.3,
                            borderWidth: 3,
                            pointBackgroundColor: '#3b82f6',
                            pointHoverRadius: 7
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                padding: 12,
                                cornerRadius: 8,
                                backgroundColor: '#0f0f1a',
                                titleFont: { family: 'Inter', size: 12, weight: 'semibold' },
                                bodyFont: { family: 'Inter', size: 12 }
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    font: { family: 'Inter', size: 11 }
                                }
                            },
                            y: {
                                grid: {
                                    color: '#f1f5f9'
                                },
                                ticks: {
                                    font: { family: 'Inter', size: 11 }
                                }
                            }
                        }
                    }
                });
            } catch (err) {
                console.error('Error parsing workout chart data:', err);
            }
        }
    }

    // --- 2. NUTRITION TREND CHART (Dual Line Chart: Calories + Protein) ---
    const nutritionChartCanvas = document.getElementById('nutritionTrendChart');
    if (nutritionChartCanvas) {
        fetch('/nutrition/api/history/')
            .then(res => res.json())
            .then(data => {
                const labels = data.map(item => item.date);
                const calories = data.map(item => item.calories);
                const protein = data.map(item => item.protein);

                new Chart(nutritionChartCanvas, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Calories (kcal)',
                                data: calories,
                                backgroundColor: 'rgba(59, 130, 246, 0.75)', // Blue
                                borderRadius: 6,
                                yAxisID: 'y'
                            },
                            {
                                label: 'Protein (g)',
                                data: protein,
                                type: 'line',
                                borderColor: '#10b981', // Green
                                borderWidth: 3,
                                pointBackgroundColor: '#10b981',
                                fill: false,
                                tension: 0.2,
                                yAxisID: 'y1'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'top',
                                labels: {
                                    font: { family: 'Inter', size: 10 }
                                }
                            },
                            tooltip: {
                                padding: 10,
                                cornerRadius: 6,
                                backgroundColor: '#0f0f1a'
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    font: { family: 'Inter', size: 10 }
                                }
                            },
                            y: {
                                position: 'left',
                                grid: {
                                    color: '#f8fafc'
                                },
                                ticks: {
                                    font: { family: 'Inter', size: 9 }
                                }
                            },
                            y1: {
                                position: 'right',
                                grid: {
                                    drawOnChartArea: false // prevent grid overlap
                                },
                                ticks: {
                                    font: { family: 'Inter', size: 9 }
                                }
                            }
                        }
                    }
                });
            })
            .catch(err => {
                console.error('Error loading nutrition history:', err);
            });
    }
});
