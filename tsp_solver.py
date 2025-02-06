import googlemaps
import pandas as pd
import time
import folium
import sys
import os
from googlemaps.exceptions import ApiError
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2
import networkx as nx  

# Initialize the Google Maps client with your API key
API_KEY = 'Replace with your actual API key'
gmaps = googlemaps.Client(key=API_KEY)

MAX_DISTANCE = 9999999  # A large number to represent unreachable routes

def geocode_addresses(addresses):
    """Geocode addresses to get latitudes and longitudes."""
    latitudes = []
    longitudes = []
    for address in addresses:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            latitudes.append(location['lat'])
            longitudes.append(location['lng'])
        else:
            latitudes.append(None)
            longitudes.append(None)
        time.sleep(0.1)  # Small delay to respect API rate limits
    return latitudes, longitudes

def split_into_batches_with_offset(locations, batch_size):
    """Split the locations into batches with offsets."""
    for i in range(0, len(locations), batch_size):
        yield locations[i:i + batch_size], i

def get_distance_matrix_in_batches(locations, batch_size=10):
    """Get the distance matrix in batches with offsets."""
    all_results = []
    
    origin_batches = list(split_into_batches_with_offset(locations, batch_size))
    destination_batches = list(split_into_batches_with_offset(locations, batch_size))
    
    for origins, origin_offset in origin_batches:
        for destinations, destination_offset in destination_batches:
            try:
                result = gmaps.distance_matrix(origins=origins, destinations=destinations, mode='driving')
            except ApiError as e:
                print(f"Error fetching distance matrix: {e}")
                continue
            all_results.append((origin_offset, destination_offset, result))
                
            # To avoid hitting rate limits, add a delay between requests
            time.sleep(1)  # Delay of 1 second
                
    return all_results

def extract_distances(results, locations):
    """Extract and organize distance values from the batch results."""
    distance_matrix = [[0 for _ in range(len(locations))] for _ in range(len(locations))]
    
    for origin_offset, destination_offset, result in results:
        for i, row in enumerate(result['rows']):
            for j, element in enumerate(row['elements']):
                if element['status'] == 'OK' and 'distance' in element:
                    distance_matrix[origin_offset + i][destination_offset + j] = element['distance']['value']
                else:
                    distance_matrix[origin_offset + i][destination_offset + j] = MAX_DISTANCE  # Uses a large value for unreachable routes
    
    return distance_matrix

# algorithum to solve the TSP using otTools
def solve_tsp_with_ortools(distance_matrix):
    """Solves the TSP using OR-Tools."""
    # Create data model
    data = {}
    data['distance_matrix'] = distance_matrix
    data['num_vehicles'] = 1
    data['depot'] = 0
    
    # Create the routing index manager
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']), data['num_vehicles'], data['depot'])
    
    # Create Routing Model
    routing = pywrapcp.RoutingModel(manager)
    
    def distance_callback(from_index, to_index):
        """Returns the distance between two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(data['distance_matrix'][from_node][to_node])
    
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    
    # Define cost of each arc
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Setting first solution heuristic
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    
    # Solve the problem
    solution = routing.SolveWithParameters(search_parameters)
    
    # Get the route
    route = []
    if solution:
        index = routing.Start(0)
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        return route
    else:
        print("No solution found!")
        return None

#Function to solve the TSP using christofides approach using networkX library
def solve_tsp_with_christofides(distance_matrix):
    """Solves the TSP using the Christofides algorithm."""
    n = len(distance_matrix) 
    G = nx.Graph()
    
    # Add edges with weights to the graph
    for u in range(n):
        for v in range(u + 1, n):
            weight = distance_matrix[u][v]
            G.add_edge(u, v, weight=weight)
            G.add_edge(v, u, weight=weight)  # Ensure undirected graph
    
    # Use the christofides function directly
    route = nx.approximation.christofides(G, weight='weight')
    
    # Since the route is a cycle, we can rotate it to start at the depot (node 0)
    if route[0] != 0:
        idx = route.index(0)
        route = route[idx:] + route[1:idx+1]
    
    # Ensure the route ends with the depot to form a cycle
    if route[-1] != 0:
        route.append(0)
    
    return route


def solve_tsp_with_christofides_2opt(distance_matrix):
    """Solves the TSP using Christofides algorithm followed by 2-opt optimization."""
    initial_route = solve_tsp_with_christofides(distance_matrix) #applying christofides approach
    if initial_route is None:
        return None
    route = two_opt(initial_route, distance_matrix) #using two-opt approach, on the uresults obtained from christofides
    return route

def solve_tsp_greedy(distance_matrix):
    """Solves the TSP using a greedy approach."""
    INT_MAX = sys.maxsize
    n = len(distance_matrix) #total no of locations to visit
    visited = [False] * n # array to keep track of visited locations
    route = [0]  # Start at depot/first location
    visited[0] = True

    #for each location finds the nearest location and visits it
    for _ in range(n - 1):
        last = route[-1]
        min_distance = INT_MAX
        next_node = None
        for j in range(n):
            if not visited[j] and distance_matrix[last][j] < min_distance:
                min_distance = distance_matrix[last][j]
                next_node = j
        if next_node is None:
            print("No unvisited node found")
            return None
        route.append(next_node)#add the next nearest location to path route
        visited[next_node] = True #marks this location as visited
    
    # Return to depot/starting location
    route.append(0)
    #returns an array of best route according to greedy approach
    return route

def solve_tsp_hybrid(distance_matrix):
    """Solves the TSP using a hybrid approach (Greedy + 2-opt)."""
    # First, get an initial route using greedy algorithm
    initial_route = solve_tsp_greedy(distance_matrix)
    if initial_route is None:
        return None
    
    # Then, improve the route using 2-opt algorithm
    route = two_opt(initial_route, distance_matrix)
    return route

def two_opt(route, distance_matrix):
    """Performs 2-opt optimization on the given route."""
    
    #Calculates the route distance for a particular route
    def calculate_route_length(route):
        return sum(distance_matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))
    
    improved = True # checks if an improvement can be made
    best_route = route.copy() #initially best possible is given route
    best_distance = calculate_route_length(best_route)

    #loops as long as shorter route can be found by edge reversal
    while improved:
        improved = False
        for i in range(1, len(best_route) - 2):
            for j in range(i + 1, len(best_route) - 1):
                if j - i == 1: # adjuscent locations don't needto be switched, thus breaks loop
                    continue
                new_route = best_route[:i] + best_route[i:j][::-1] + best_route[j:] #swaps two pairs of edges (edge reversal)
                new_distance = calculate_route_length(new_route) #checks efficiency of new route
                if new_distance < best_distance:
                    best_route = new_route
                    best_distance = new_distance
                    improved = True
        route = best_route
    
    #returns an array of best route according to greedy approach
    return route

def plot_route(route, locations_df, filename):
    """Plots the route on a map using folium and saves it to an HTML file."""
    # Center of the map (we'll use the depot's coordinates)
    depot_lat = locations_df.iloc[route[0]]['Latitude']
    depot_lon = locations_df.iloc[route[0]]['Longitude']
    map_center = (depot_lat, depot_lon)

    # Create a folium map
    m = folium.Map(location=map_center, zoom_start=12)

    # Add markers for each location, starting numbering from 1
    for idx, node in enumerate(route[:-1]):
        lat = locations_df.iloc[node]['Latitude']
        lon = locations_df.iloc[node]['Longitude']
        stop_number = idx + 1  # Adjust stop number to start from 1

        folium.Marker(
            location=(lat, lon),
            popup=f"Stop {stop_number}: {locations_df.iloc[node]['Address']}",
            icon=folium.DivIcon(
                icon_size=(20, 20),
                icon_anchor=(10, 10),
                html=f"<div style='font-size: 12pt;'>{stop_number}</div>"
            )
        ).add_to(m)

    # Draw route lines
    for i in range(len(route) - 1):
        origin = (locations_df.iloc[route[i]]['Latitude'], locations_df.iloc[route[i]]['Longitude'])
        destination = (locations_df.iloc[route[i + 1]]['Latitude'], locations_df.iloc[route[i + 1]]['Longitude'])

        try:
            directions_result = gmaps.directions(origin, destination, mode='driving')
            if directions_result:
                steps = directions_result[0]['legs'][0]['steps']
                path = []
                for step in steps:
                    polyline = step['polyline']['points']
                    decoded_points = googlemaps.convert.decode_polyline(polyline)
                    path.extend([(point['lat'], point['lng']) for point in decoded_points])
                folium.PolyLine(locations=path, color='blue', weight=5, opacity=0.8).add_to(m)
        except ApiError as e:
            print(f"Error fetching directions: {e}")
            folium.PolyLine(locations=[origin, destination], color='red', weight=2, opacity=0.8).add_to(m)

        time.sleep(1)  # Small delay to respect API rate limits

    # Ensure the directory exists
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    # Save the map to an HTML file
    m.save(filename)
    print(f"Route map saved to '{filename}'.")
    
    
def calculate_route_distance(route, distance_matrix):
    """Calculates the total distance of the given route."""
    total_distance = sum(distance_matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))
    return total_distance