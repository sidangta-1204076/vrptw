from flask import Flask, request, render_template, jsonify
import pandas as pd
import numpy as np
import requests
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import osmnx as ox
import networkx as nx

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/solve', methods=['GET', 'POST'])
def solve_page():
    if request.method == 'GET':
        return render_template('solve.html')
    elif request.method == 'POST':
        if request.headers['Content-Type'] != 'application/json':
            return jsonify({'error': 'Content-Type must be application/json'}), 415
        
        data = request.get_json()
        print("Received data:", data)  # Debugging line
        locations = data['locations']
        demands = data['demands']
        vehicle_count = 1
        vehicle_type = float(data['vehicle_type'])
        depot = 0  # Starting point index

        # Ensure demands are within limits based on vehicle type
        max_demand = 10 if vehicle_type in [58.5, 62] else 15
        if any(d > max_demand for d in demands):
            return jsonify({'error': 'Demand exceeds vehicle capacity.'}), 400

        # Convert locations to DataFrame
        df = pd.DataFrame(locations, columns=['latitude', 'longitude'])

        # Convert coordinates to dictionary for compute_distance_matrix function
        nodes_coordinates = {str(i): (lat, lon) for i, (lat, lon) in enumerate(locations)}

        # Compute the distance and time matrices using OSRM
        distance_matrix, time_matrix = compute_distance_matrix_osrm(locations)

        # Create the routing index manager
        manager = pywrapcp.RoutingIndexManager(len(distance_matrix), vehicle_count, depot)

        # Create Routing Model
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            """Returns the distance between the two nodes."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Setting first solution heuristic
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

        # Solve the problem
        solution = routing.SolveWithParameters(search_parameters)

        # Get routes and details
        routes, route_details, total_distance, total_duration, total_fuel_consumption = get_routes_and_details(
            manager, routing, solution, vehicle_count, distance_matrix, time_matrix, vehicle_type)

        # Format route for the map using OSRM
        formatted_route = get_osrm_route(locations)
        print("Formatted route:", formatted_route)  # Debugging line

        return jsonify({
            'route': formatted_route,
            'locations': locations,
            'route_details': route_details,
            'total_distance': total_distance,
            'total_duration': total_duration,
            'total_fuel_consumption': total_fuel_consumption
        })

def compute_distance_matrix_osrm(locations):
    osrm_url = 'http://router.project-osrm.org/table/v1/driving/'
    coordinates = ';'.join([f"{lon},{lat}" for lat, lon in locations])
    osrm_request = f"{osrm_url}{coordinates}?annotations=distance,duration"

    response = requests.get(osrm_request)
    if response.status_code != 200:
        print("OSRM request failed with status code:", response.status_code)  # Debugging line
        return jsonify({'error': 'OSRM request failed'}), 500

    osrm_data = response.json()
    distance_matrix = osrm_data['distances']
    duration_matrix = osrm_data['durations']
    
    return np.array(distance_matrix), np.array(duration_matrix)

def get_osrm_route(locations):
    # OSRM request for route
    osrm_url = 'http://router.project-osrm.org/route/v1/driving/'
    coordinates = ';'.join([f"{lon},{lat}" for lat, lon in locations])
    osrm_request = f"{osrm_url}{coordinates}?overview=full&geometries=geojson"

    response = requests.get(osrm_request)
    if response.status_code != 200:
        print("OSRM request failed with status code:", response.status_code)  # Debugging line
        return jsonify({'error': 'OSRM request failed'}), 500
    
    osrm_data = response.json()
    route = osrm_data['routes'][0]['geometry']['coordinates']
    formatted_route = [[lat, lon] for lon, lat in route]  # Swap coordinates for Leaflet
    return formatted_route

def index_to_label(index):
    return chr(ord('A') + index)

def get_routes_and_details(manager, routing, solution, vehicle_count, distance_matrix, time_matrix, vehicle_type):
    routes = []
    route_details = []
    total_distance = 0
    total_duration = 0
    total_fuel_consumption = 0
    for vehicle_id in range(vehicle_count):
        index = routing.Start(vehicle_id)
        route = []
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        # Ensure the vehicle returns to the depot
        if route[-1] != route[0]:
            route.append(manager.IndexToNode(routing.Start(vehicle_id)))
        if len(route) > 1:
            routes.append(route)

        # Collect route details
        for i in range(len(route) - 1):  # Include return to depot
            from_node = route[i]
            to_node = route[i + 1]
            distance = distance_matrix[from_node][to_node] / 1000  # Convert to km
            duration = time_matrix[from_node][to_node] / 60  # Convert to minutes
            fuel_consumption = distance / vehicle_type  # Fuel consumption in liters
            # Skip the last entry if it's the return to depot with zero values
            if distance > 0 or duration > 0:
                route_details.append({
                    'from': index_to_label(from_node),
                    'to': index_to_label(to_node),
                    'distance': distance,
                    'duration': duration,
                    'fuel_consumption': fuel_consumption
                })
                total_distance += distance
                total_duration += duration
                total_fuel_consumption += fuel_consumption

    return routes, route_details, total_distance, total_duration, total_fuel_consumption

if __name__ == '__main__':
    app.run(debug=True)