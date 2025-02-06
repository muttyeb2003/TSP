//Javascript to handle frontend rendering of the Traveling-Sales-Man Problem

// Gets a excel file from user by adding click event lisner to 'chose file' button
document.getElementById('choose-file-button').addEventListener('click', function() {
    document.getElementById('file-input').click();
});

// Initialize variables
let selectedFile = null;
let algorithmResults = [];
let eventListenersAdded = false;

// Adds change event listener to the file input element, gets file from user
document.getElementById('file-input').addEventListener('change', function() {
    selectedFile = this.files[0];
    if (selectedFile) {
        // Display the selected file name
        document.getElementById('file-name').textContent = selectedFile.name;
    } else {
        document.getElementById('file-name').textContent = 'No file chosen';
    }
});

document.getElementById('upload-file-button').addEventListener('click', function() {
    if (!selectedFile) {
        alert("Please choose a file first.");
        return;
    }
    let formData = new FormData();
    formData.append('file', selectedFile);

    // Send a POST request to the '/upload' endpoint with the file data
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.addresses) {
            let previewList = document.getElementById('preview-list');
            previewList.innerHTML = '';
            data.addresses.forEach(address => {
                let li = document.createElement('li');
                li.textContent = address;
                previewList.appendChild(li);
            });
        } else if (data.error) {
            alert(data.error);
        }
    })
    .catch(error => console.error('Error:', error));
});

document.getElementById('optimize-route-button').addEventListener('click', function() {
    document.getElementById('loading').style.display = 'block';
    // Simulate a delay before sending the request
    setTimeout(() => {
        //Sends Post request to get the TSP solutions using differnt algorithms from the python file
        fetch('/solve_tsp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({'algorithms': ['ortools', 'christofides2opt', 'greedy2opt']})
        })
        .then(response => response.json())
        .then(data => {
            // Hide the loading indicator
            document.getElementById('loading').style.display = 'none';
            if (data.results && data.results.length > 0) {
                algorithmResults = data.results;
                // Store and sort the algorithm results based on total distance
                algorithmResults.sort((a, b) => a.total_distance - b.total_distance);

                // Update the UI with the results of each algorithm
                data.results.forEach(result => {
                    if (result.error) {
                        alert(`Algorithm ${result.algorithm}: ${result.error}`);
                        return;
                    }
                    // Update the algorithm card with distance and route
                    const algorithmCard = document.getElementById(`algorithm-${result.algorithm}`);
                    algorithmCard.querySelector('.distance').textContent = result.total_distance;
                    const routeStops = algorithmCard.querySelector('.route-stops');
                    routeStops.innerHTML = '';
                    result.route.forEach(address => {
                        let li = document.createElement('li');
                        li.textContent = address;
                        routeStops.appendChild(li);
                    });
                });

                document.getElementById('section-2').style.display = 'block';
                document.getElementById('section-3').style.display = 'block';

                //updates the UI with the best algorithm's results.
                populateBestAlgorithmSection(algorithmResults[0]);

                // Populate the algorithm selection dropdown
                const algorithmSelect = document.getElementById('algorithm-select');
                algorithmSelect.innerHTML = '';
                algorithmResults.forEach((result, index) => {
                    const option = document.createElement('option');
                    option.value = index;
                    option.textContent = `${index + 1}. ${result.algorithm}`;
                    algorithmSelect.appendChild(option);
                });

                if (!eventListenersAdded) {
                    algorithmSelect.addEventListener('change', function() {
                        const selectedIndex = this.value;
                        populateBestAlgorithmSection(algorithmResults[selectedIndex]);
                    });
                    eventListenersAdded = true;
                }

            } else if (data.error) {
                alert(data.error);
            } else {
                alert('An unexpected error occurred.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while optimizing the route.');
            document.getElementById('loading').style.display = 'none';
        });
    }, 2000);
});

// Function to populate the best algorithm section with result data
function populateBestAlgorithmSection(result) {
    console.log(`Populating best algorithm section for: ${result.algorithm}`);
    // Update the best algorithm name and distance
    document.getElementById('best-algorithm').textContent = result.algorithm;
    document.getElementById('best-distance').textContent = result.total_distance;
    const bestRouteStops = document.getElementById('best-route-stops');
    bestRouteStops.innerHTML = '';
    result.route.forEach(address => {
        let li = document.createElement('li');
        li.textContent = address;
        bestRouteStops.appendChild(li);
    });

    // Show the map loading indicator and hide the route map
    document.getElementById('map-loading').style.display = 'block';
    document.getElementById('route-map').style.display = 'none';
  
    // Simulate a delay before fetching the route map
    setTimeout(() => {
        console.log(`Calling /plot_route for algorithm: ${result.algorithm}`);
        fetch('/plot_route', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({'algorithm': result.algorithm})
        })
        .then(response => response.json())
        .then(data => {
            if (data.map_url) {
                 // Set the source of the route map image
                document.getElementById('route-map').src = data.map_url;
                // when the map image loads, display it and hide the loading indicator
                document.getElementById('route-map').onload = function() {
                    document.getElementById('map-loading').style.display = 'none';
                    document.getElementById('route-map').style.display = 'block';
                };
            } else if (data.error) {
                alert(data.error);
                document.getElementById('map-loading').style.display = 'none';
            }
        });
    }, 2000);
}
