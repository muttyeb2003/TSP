from flask import Flask, render_template, request, jsonify, send_from_directory
import pandas as pd
import os
import tsp_solver
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['STATIC_FOLDER'] = 'static'

# Ensure the upload and static folders exist
for folder in [app.config['UPLOAD_FOLDER'], app.config['STATIC_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Global variables to store data between requests
addresses = []
locations_df = None
distance_matrix = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global addresses
    file = request.files.get('file')
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try:
            df = pd.read_excel(filepath, header=None)
            df.columns = ['ID', 'Address']
            addresses = df['Address'].tolist()
            return jsonify({'addresses': addresses})
        except Exception as e:
            return jsonify({'error': f'Error processing the file: {str(e)}'})
    return jsonify({'error': 'No file uploaded'})

@app.route('/solve_tsp', methods=['POST'])
def solve_tsp():
    global addresses, locations_df, distance_matrix
    data = request.get_json()
    algorithms = data.get('algorithms', [])
    if not addresses:
        return jsonify({'error': 'No addresses found'})

    # Geocode addresses and compute distance matrix
    latitudes, longitudes = tsp_solver.geocode_addresses(addresses)
    locations_df = pd.DataFrame({
        'Address': addresses,
        'Latitude': latitudes,
        'Longitude': longitudes
    })

    # Check if locations were geocoded correctly
    if locations_df.isnull().values.any():
        return jsonify({'error': 'Some addresses could not be geocoded'})

    distance_results = tsp_solver.get_distance_matrix_in_batches(addresses)
    distance_matrix = tsp_solver.extract_distances(distance_results, addresses)
    
    results = []
    for algorithm in algorithms:
        if algorithm == 'ortools':
            route = tsp_solver.solve_tsp_with_ortools(distance_matrix)
        elif algorithm == 'christofides2opt':
            route = tsp_solver.solve_tsp_with_christofides_2opt(distance_matrix)
        elif algorithm == 'greedy2opt':
            route = tsp_solver.solve_tsp_hybrid(distance_matrix)
        else:
            route = None

        if route is None:
            result = {'algorithm': algorithm, 'error': 'No solution found'}
        else:
            total_distance = tsp_solver.calculate_route_distance(route, distance_matrix)
            route_addresses = [addresses[i] for i in route]
            result = {'algorithm': algorithm, 'route': route_addresses, 'total_distance': total_distance}
        results.append(result)

    return jsonify({'results': results})

@app.route('/plot_route', methods=['POST'])
def plot_route():
    global locations_df, distance_matrix
    data = request.get_json()
    algorithm = data.get('algorithm')
    
    if algorithm == 'ortools':
        route = tsp_solver.solve_tsp_with_ortools(distance_matrix)
        filename = os.path.join(app.config['STATIC_FOLDER'], 'ortools_route_map.html')
    elif algorithm == 'christofides2opt':
        route = tsp_solver.solve_tsp_with_christofides_2opt(distance_matrix)
        filename = os.path.join(app.config['STATIC_FOLDER'], 'christofides2opt_route_map.html')
    elif algorithm == 'greedy2opt':
        route = tsp_solver.solve_tsp_hybrid(distance_matrix)
        filename = os.path.join(app.config['STATIC_FOLDER'], 'greedy2opt_route_map.html')
    else:
        return jsonify({'error': 'Invalid algorithm'})

    if route is None:
        return jsonify({'error': 'No solution found'})

    tsp_solver.plot_route(route, locations_df, filename)
    map_filename = os.path.basename(filename)
    map_url = '/static/' + map_filename
    return jsonify({'map_url': map_url})

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.config['STATIC_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
