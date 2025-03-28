import pygame
import numpy as np
import sys
import time
import random
import pygame_gui
import json
import os
import math
from tkinter import filedialog
import pandas as pd


pygame.init()


SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 1000
BG_COLOR = (240, 240, 240)
CITY_COLOR = (0, 100, 200)
ANT_COLOR = (200, 0, 0)
PATH_COLOR = (150, 150, 150)
PHEROMONE_COLOR = (0, 200, 0)
TEXT_COLOR = (50, 50, 50)
FONT_SIZE = 16

def haversine(lon1, lat1, lon2, lat2):
    
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371  
    return c * r

def scale_geo_coords(coords_data, width, height, padding=50):
    
    if not coords_data:
        return []
        
    lats = [point['lat'] for point in coords_data]
    lons = [point['lng'] for point in coords_data]
    
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    screen_width = width - 300 - padding * 2  
    screen_height = height - padding * 2
    
    scaled_cities = []
    for city in coords_data:
        x_ratio = 0.0 if max_lon == min_lon else (city['lng'] - min_lon) / (max_lon - min_lon)
        y_ratio = 0.0 if max_lat == min_lat else (city['lat'] - min_lat) / (max_lat - min_lat)
        
        x = padding + x_ratio * screen_width
        y = padding + (1 - y_ratio) * screen_height  
        
        scaled_cities.append({
            'name': city.get('name', 'Unknown'),
            'x': x,
            'y': y,
            'lat': city['lat'],
            'lng': city['lng'],
            'is_geo': True
        })
        
    return scaled_cities

class AntColonyOptimization:
    def __init__(self, cities, n_ants=10, decay=0.95, alpha=1.0, beta=2.0):
        self.cities = cities
        self.n_cities = len(cities)
        self.is_geo = any(city.get('is_geo', False) for city in cities) if cities else False
        self.distances = self.calculate_distances()
        self.pheromones = np.ones((self.n_cities, self.n_cities)) / self.n_cities
        self.n_ants = n_ants
        self.decay = decay
        self.alpha = alpha
        self.beta = beta
        
        self.best_path = None
        self.best_path_length = float('inf')
        self.iteration_best_paths = []
        self.iteration_best_lengths = []
        
        self.ant_positions = []  
        self.ant_trails = []     
        self.current_iteration = 0
        
    def calculate_distances(self):
        distances = np.zeros((self.n_cities, self.n_cities))
        
        print(f"Calculating distances between {self.n_cities} cities")
        print(f"Geographic mode: {self.is_geo}")
        
        for i in range(self.n_cities):
            for j in range(self.n_cities):
                if i != j:
                    if self.is_geo and 'lat' in self.cities[i] and 'lng' in self.cities[i]:
                        distances[i, j] = haversine(
                            self.cities[i]['lng'], self.cities[i]['lat'],
                            self.cities[j]['lng'], self.cities[j]['lat']
                        )
                    else:
                        distances[i, j] = np.sqrt(
                            (self.cities[i]['x'] - self.cities[j]['x'])**2 + 
                            (self.cities[i]['y'] - self.cities[j]['y'])**2
                        )
                else:
                    distances[i, j] = np.inf
        
        if self.is_geo:
            
            count = 0
            for i in range(self.n_cities):
                for j in range(i+1, self.n_cities):
                    if count < 5:  # Show just 5 examples to avoid flooding terminal
                        print(f"From {self.cities[i]['name']} to {self.cities[j]['name']}: {distances[i, j]:.2f} km")
                        count += 1
            
            all_distances = [distances[i, j] for i in range(self.n_cities) for j in range(i+1, self.n_cities)]
            if all_distances:
                print(f"Minimum distance: {min(all_distances):.2f} km")
                print(f"Maximum distance: {max(all_distances):.2f} km")
                print(f"Average distance: {sum(all_distances)/len(all_distances):.2f} km")
            
        
        return distances
    
    def run_iteration(self):
        if self.n_cities < 2:
            return None, float('inf')  # Need at least 2 cities
            
        self.ant_positions = [np.random.randint(0, self.n_cities) for _ in range(self.n_ants)]
        self.ant_trails = [[pos] for pos in self.ant_positions]
        
        all_paths = []
        for ant in range(self.n_ants):
            path = self.gen_path(self.ant_positions[ant])
            all_paths.append(path)
            
        self.spread_pheromone(all_paths)
        self.pheromones = self.pheromones * self.decay
        
        iteration_best_path = min(all_paths, key=lambda x: self.path_length(x))
        iteration_best_length = self.path_length(iteration_best_path)
        self.iteration_best_paths.append(iteration_best_path)
        self.iteration_best_lengths.append(iteration_best_length)
        
        if iteration_best_length < self.best_path_length:
            self.best_path = iteration_best_path
            self.best_path_length = iteration_best_length
            
        self.current_iteration += 1
        return iteration_best_path, iteration_best_length
    
    def gen_path(self, start):
        path = [start]
        visited = set([start])
        
        while len(visited) < self.n_cities:
            current = path[-1]
            unvisited = list(set(range(self.n_cities)) - visited)
            
            probabilities = self.calculate_probabilities(current, unvisited)
            
            next_city = np.random.choice(unvisited, p=probabilities)
            
            path.append(next_city)
            visited.add(next_city)
            
            ant_idx = self.ant_positions.index(start)
            self.ant_trails[ant_idx].append(next_city)
            
        path.append(path[0])
        
        ant_idx = self.ant_positions.index(start)
        self.ant_trails[ant_idx].append(path[0])
        
        return path
    
    def calculate_probabilities(self, current, unvisited):
        probabilities = []
        denominator = 0
        
        for city in unvisited:
            pheromone = self.pheromones[current, city]
            distance = self.distances[current, city]
            numerator = pheromone**self.alpha * (1.0/distance)**self.beta
            denominator += numerator
            probabilities.append(numerator)
        
        if denominator == 0:
            return np.ones(len(unvisited)) / len(unvisited)
        probabilities = np.array(probabilities) / denominator
        return probabilities
    
    def spread_pheromone(self, all_paths):
        for path in all_paths:
            path_length = self.path_length(path)
            for i in range(len(path) - 1):
                self.pheromones[path[i], path[i+1]] += 1.0 / path_length
    
    def path_length(self, path):
        length = 0
        for i in range(len(path) - 1):
            length += self.distances[path[i], path[i+1]]
        return length
    
    def update_coords(self, cities):
        self.cities = cities
        self.n_cities = len(cities)
        self.is_geo = any(city.get('is_geo', False) for city in cities) if cities else False
        print(f"\nACO updated with {self.n_cities} cities (Geographic: {self.is_geo})")
        
        self.distances = self.calculate_distances()
        self.pheromones = np.ones((self.n_cities, self.n_cities)) / self.n_cities
        self.best_path = None
        self.best_path_length = float('inf')
        self.iteration_best_paths = []
        self.iteration_best_lengths = []
        self.current_iteration = 0
        
        self.ant_positions = []
        self.ant_trails = []
    
    def get_ant_positions(self):
        return self.ant_positions
    
    def get_ant_trails(self):
        return self.ant_trails
    
    def get_best_path(self):
        return self.best_path
    
    def get_best_path_length(self):
        return self.best_path_length
    
    def get_pheromone_levels(self):
        return self.pheromones

class ACOVisualizer:
    def __init__(self, n_cities=20, n_ants=10, width=SCREEN_WIDTH, height=SCREEN_HEIGHT):
        self.width = width
        self.height = height
        self.n_cities = n_cities
        self.n_ants = n_ants
        
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Ant Colony Optimization Visualization")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, FONT_SIZE)
        
        self.ui_manager = pygame_gui.UIManager((width, height))
        
        self.cities = []
        self.generate_cities()
        
        self.aco = AntColonyOptimization(
            self.cities, 
            n_ants=n_ants, 
            decay=0.95, 
            alpha=1.0, 
            beta=2.0
        )
        
        self.paused = True
        self.speed = 10  
        self.step_mode = False
        self.show_pheromones = True
        self.target_iteration = 100  # Default target iteration
        self.running_to_target = False  # Flag for animated run to target
        
        self.manual_mode = False
        
        self.create_ui()
        
    def generate_cities(self):
        self.cities = []
        
        padding = 50
        city_area_width = self.width - 300 - padding * 2  # Reserve 300px for UI panel
        city_area_height = self.height - padding * 2
        
        for i in range(self.n_cities):
            x = random.randint(padding, padding + city_area_width)
            y = random.randint(padding, padding + city_area_height)
            self.cities.append({
                'name': f"City {i+1}",
                'x': x,
                'y': y,
                'is_geo': False
            })
    
    def add_city(self, pos):
        # Ensure we're not clicking in the UI panel area
        if pos[0] < self.width - 300:
            self.cities.append(pos)
            self.n_cities = len(self.cities)
            # Update parameters in UI
            self.param_sliders['cities'].set_current_value(self.n_cities)
            # Update ACO instance
            self.aco.update_coords(self.cities)
    
    def clear_cities(self):
        self.cities = []
        self.n_cities = 0
        self.aco.update_coords(self.cities)
    
    def create_ui(self):
        # UI panel area
        panel_rect = pygame.Rect(self.width - 280, 0, 280, self.height)
        
        # Buttons
        button_width = 120
        button_height = 30
        button_margin = 10
        
        y_pos = 20
        
        self.start_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, button_width, button_height),
            text='Start',
            manager=self.ui_manager
        )
        
        self.pause_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + button_width + 20, y_pos, button_width, button_height),
            text='Pause',
            manager=self.ui_manager
        )
        
        y_pos += button_height + button_margin
        
        self.load_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, button_width, button_height),
            text='Load Cities',
            manager=self.ui_manager
        )
        
        self.save_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + button_width + 20, y_pos, button_width, button_height),
            text='Save Cities',
            manager=self.ui_manager
        )
        
        y_pos += button_height + button_margin
        
        self.step_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, button_width, button_height),
            text='Step',
            manager=self.ui_manager
        )
        
        self.reset_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + button_width + 20, y_pos, button_width, button_height),
            text='Reset',
            manager=self.ui_manager
        )
        
        y_pos += button_height + button_margin
        
        self.manual_mode_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, button_width, button_height),
            text='Add Cities Manually',
            manager=self.ui_manager
        )
        
        self.clear_cities_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + button_width + 20, y_pos, button_width, button_height),
            text='Clear Cities',
            manager=self.ui_manager
        )
        
        y_pos += button_height + button_margin * 2
        
        self.speed_slider_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 20),
            text='Animation Speed',
            manager=self.ui_manager
        )
        
        y_pos += 25
        
        self.speed_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 20),
            start_value=self.speed,
            value_range=(1, 60),
            manager=self.ui_manager
        )
        
        y_pos += 30 + button_margin
        
        self.param_labels = {}
        self.param_sliders = {}
        
        params = {
            'cities': {'label': 'Cities', 'value': self.n_cities, 'range': (5, 50)},
            'ants': {'label': 'Ants', 'value': self.n_ants, 'range': (5, 100)},
            'alpha': {'label': 'Alpha (Pheromone Weight)', 'value': 1.0, 'range': (0.1, 5.0)},
            'beta': {'label': 'Beta (Distance Weight)', 'value': 2.0, 'range': (0.1, 10.0)},
            'decay': {'label': 'Pheromone Decay', 'value': 0.95, 'range': (0.5, 0.99)}
        }
        
        for param, details in params.items():
            self.param_labels[param] = pygame_gui.elements.UILabel(
                relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 20),
                text=details['label'],
                manager=self.ui_manager
            )
            
            y_pos += 25
            
            self.param_sliders[param] = pygame_gui.elements.UIHorizontalSlider(
                relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 20),
                start_value=details['value'],
                value_range=details['range'],
                manager=self.ui_manager
            )
            
            y_pos += 30 + button_margin
        
        # Add buttons for running to target iteration
        self.run_to_target_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, button_width, button_height),
            text='Run to Target',
            manager=self.ui_manager
        )
        
        self.reset_iteration_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + button_width + 20, y_pos, button_width, button_height),
            text='Reset Iteration',
            manager=self.ui_manager
        )
        
        y_pos += button_height + button_margin * 2
        
        self.target_iter_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 20),
            text='Target Iteration',
            manager=self.ui_manager
        )
        
        y_pos += 25
        
        self.target_iter_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 20),
            start_value=100,
            value_range=(1, 1000),
            manager=self.ui_manager
        )
        
        y_pos += 30 + button_margin
        
        self.apply_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 60, y_pos, 150, button_height),
            text='Apply Parameters',
            manager=self.ui_manager
        )
        
        y_pos += button_height + button_margin * 2
        
        self.show_pheromones_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 60, y_pos, 150, button_height),
            text='Toggle Pheromones',
            manager=self.ui_manager
        )
        
        y_pos += button_height + button_margin * 3
        
        # Mode indicator
        self.mode_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 20),
            text='Current Mode: Normal',
            manager=self.ui_manager
        )
        
        y_pos += 25
        
        self.instructions_label = pygame_gui.elements.UITextBox(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 100),
            html_text="<b>Instructions:</b><br>"
                    "- Click 'Add Cities Manually' to place cities<br>"
                    "- Click anywhere to add a city<br>"
                    "- Press 'Apply Parameters' when done<br>"
                    "- Use 'Start/Pause/Step' to control simulation",
            manager=self.ui_manager
        )
        
        self.save_image_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, button_width * 2 + 10, button_height),
            text='Save Current View as Image',
            manager=self.ui_manager
        )
    
        y_pos += 120  # Add enough space after instructions text box
        
        self.save_image_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 35),  # Make it wider and taller
            text='Save Screenshot as PNG',  # More descriptive text
            manager=self.ui_manager,
            object_id=pygame_gui.core.ObjectID(class_id='@important_buttons')  # Special styling
        )
        
        y_pos += 45
        self.save_data_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_rect.left + 10, y_pos, 250, 35),
            text='Save City Data',
            manager=self.ui_manager
        )
    
    def apply_parameters(self):
        n_cities = int(self.param_sliders['cities'].get_current_value())
        n_ants = int(self.param_sliders['ants'].get_current_value())
        alpha = self.param_sliders['alpha'].get_current_value()
        beta = self.param_sliders['beta'].get_current_value()
        decay = self.param_sliders['decay'].get_current_value()
        
        if n_cities != self.n_cities and not self.manual_mode:
            self.n_cities = n_cities
            self.generate_cities()
        
        self.aco = AntColonyOptimization(
            self.cities, 
            n_ants=n_ants, 
            decay=decay, 
            alpha=alpha, 
            beta=beta
        )
        
        self.n_ants = n_ants
        self.paused = True
    
    def draw(self):
        self.screen.fill(BG_COLOR)
        
        # Draw panel background
        panel_rect = pygame.Rect(self.width - 280, 0, 280, self.height)
        pygame.draw.rect(self.screen, (220, 220, 220), panel_rect)
        
        if self.show_pheromones and self.n_cities > 1:
            pheromones = self.aco.get_pheromone_levels()
            max_pheromone = np.max(pheromones) if np.max(pheromones) > 0 else 1
            
            for i in range(self.n_cities):
                for j in range(i+1, self.n_cities):
                    if pheromones[i, j] > 0:
                        level = max(pheromones[i, j], pheromones[j, i])
                        norm_level = level / max_pheromone
                        width = int(1 + 5 * norm_level)
                        alpha = int(50 + 200 * norm_level)
                        
                        line_color = (*PHEROMONE_COLOR, alpha)
                        
                        city_i = self.cities[i]
                        city_j = self.cities[j]
                        
                        start_pos = (city_i['x'], city_i['y']) if isinstance(city_i, dict) else city_i
                        end_pos = (city_j['x'], city_j['y']) if isinstance(city_j, dict) else city_j
                        
                        pygame.draw.line(self.screen, line_color, start_pos, end_pos, width)
        
        if self.n_cities > 1:
            for trail in self.aco.get_ant_trails():
                if len(trail) > 1:
                    # Convert city indices to screen positions
                    points = []
                    for city_idx in trail:
                        city = self.cities[city_idx]
                        if isinstance(city, dict):
                            points.append((city['x'], city['y']))
                        else:
                            points.append(city)
                    pygame.draw.lines(self.screen, PATH_COLOR, False, points, 1)
        
        # Draw best path if available
        best_path = self.aco.get_best_path()
        if best_path:
            points = []
            for city_idx in best_path:
                city = self.cities[city_idx]
                if isinstance(city, dict):
                    points.append((city['x'], city['y']))
                else:
                    points.append(city)
            pygame.draw.lines(self.screen, (0, 0, 0), True, points, 2)
        
        for i, city in enumerate(self.cities):
            if isinstance(city, dict):
                x, y = city['x'], city['y']
            else:
                x, y = city
                
            pygame.draw.circle(self.screen, CITY_COLOR, (x, y), 8)
        
        for i, city in enumerate(self.cities):
            if isinstance(city, dict):
                x, y = city['x'], city['y']
                name = city.get('name', str(i))
            else:
                x, y = city
                name = str(i)
                
            name_label = self.font.render(name, True, TEXT_COLOR)
            
            label_bg = pygame.Rect(x + 10, y - 10, 
                                name_label.get_width() + 4, 
                                name_label.get_height() + 2)
            
            bg_surface = pygame.Surface((label_bg.width, label_bg.height), pygame.SRCALPHA)
            bg_surface.fill((255, 255, 255, 200))  # White with alpha
            self.screen.blit(bg_surface, label_bg)
            
            self.screen.blit(name_label, (x + 12, y - 9))
        
        # Draw ants
        if self.n_cities > 1:
            for ant_idx, pos in enumerate(self.aco.get_ant_positions()):
                if ant_idx < len(self.aco.get_ant_trails()) and self.aco.get_ant_trails()[ant_idx]:
                    trail = self.aco.get_ant_trails()[ant_idx]
                    if trail:
                        last_pos = trail[-1]
                        city = self.cities[last_pos]
                        if isinstance(city, dict):
                            ant_x, ant_y = city['x'], city['y']
                        else:
                            ant_x, ant_y = city
                        pygame.draw.circle(self.screen, ANT_COLOR, (ant_x, ant_y), 5)
        
        # Draw information
        info_text = [
            f"Iteration: {self.aco.current_iteration} / {int(self.target_iter_slider.get_current_value())}",
            f"Best path length: {self.aco.get_best_path_length():.2f} {'km' if self.aco.is_geo else 'units'}",
            f"Ants: {self.n_ants}",
            f"Cities: {self.n_cities}",
            f"Speed: {self.speed} FPS",
            f"Mode: {'Geographic' if self.aco.is_geo else 'Normal'}"
        ]
        
        info_y = 10
        for text in info_text:
            label = self.font.render(text, True, TEXT_COLOR)
            self.screen.blit(label, (10, info_y))
            info_y += 25
        
        # Update mode label
        self.mode_label.set_text(f"Current Mode: {'Manual City Placement' if self.manual_mode else 'Normal'}")
        
        # Update UI
        self.ui_manager.draw_ui(self.screen)
        
        # Update display
        pygame.display.flip()
    
    def run(self):
        running = True
        
        while running:
            time_delta = self.clock.tick(self.speed) / 1000.0
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
                    if self.manual_mode:
                        self.add_city(event.pos)
                
                if event.type == pygame.USEREVENT:
                    if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                        if event.ui_element == self.start_button:
                            self.paused = False
                            self.manual_mode = False
                        elif event.ui_element == self.pause_button:
                            self.paused = True
                        elif event.ui_element == self.step_button:
                            self.aco.run_iteration()
                        elif event.ui_element == self.reset_button:
                            self.apply_parameters()
                        elif event.ui_element == self.apply_button:
                            self.manual_mode = False
                            self.apply_parameters()
                        elif event.ui_element == self.show_pheromones_button:
                            self.show_pheromones = not self.show_pheromones
                        elif event.ui_element == self.manual_mode_button:
                            self.manual_mode = not self.manual_mode
                            self.paused = True
                        elif event.ui_element == self.clear_cities_button:
                            self.clear_cities()
                            self.param_sliders['cities'].set_current_value(0)
                        elif event.ui_element == self.load_button:
                            self.load_cities_dialog()
                        elif event.ui_element == self.save_button:
                            self.save_cities_dialog()
                        elif event.ui_element == self.run_to_target_button:
                            self.run_to_target()
                        elif event.ui_element == self.reset_iteration_button:
                            # Reset iterations counter
                            self.aco.current_iteration = 0
                            self.aco.iteration_best_paths = []
                            self.aco.iteration_best_lengths = []
                        elif event.ui_element == self.save_image_button:
                            # Use direct filedialog from tkinter
                            import tkinter as tk
                            from tkinter import filedialog
                            
                            root = tk.Tk()
                            root.withdraw()  # Hide the main window
                            
                            file_path = filedialog.asksaveasfilename(
                                title="Save Visualization as Image",
                                filetypes=[("PNG Image", "*.png")],
                                defaultextension=".png"
                            )
                            
                            if file_path:
                                self.save_visualization_as_image(file_path)
                                # Show confirmation on screen
                                print(f"Image saved to {file_path}")
                        elif event.ui_element == self.save_data_button:
                            self.save_cities_dialog()
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s:  
                        import tkinter as tk
                        from tkinter import filedialog
                        
                        root = tk.Tk()
                        root.withdraw()  # Hide the main window
                        
                        file_path = filedialog.asksaveasfilename(
                            title="Save Visualization as Image",
                            filetypes=[("PNG Image", "*.png")],
                            defaultextension=".png"
                        )
                        
                        if file_path:
                            self.save_visualization_as_image(file_path)
                            print(f"Image saved to {file_path}")
                
                elif event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                    if event.ui_element == self.speed_slider:
                        self.speed = int(event.value)
                
                self.ui_manager.process_events(event)
            
            if not self.paused and not self.manual_mode and self.n_cities > 1:
                self.aco.run_iteration()
                
                if self.running_to_target:
                    target = int(self.target_iter_slider.get_current_value())
                    if self.aco.current_iteration >= target:
                        self.running_to_target = False
                        self.paused = True  # Pause when we reach the target
            
            self.ui_manager.update(time_delta)
            
            self.draw()
        
        pygame.quit()
    
    def load_cities_dialog(self):
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        file_path = filedialog.askopenfilename(
            title="Load Cities",
            filetypes=[
                ("All Supported Files", "*.txt *.csv *.json"),
                ("Text files", "*.txt"), 
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            cities = load_cities_from_file(file_path)
            if cities:
                self.cities = cities
                self.n_cities = len(cities)
                self.aco.update_coords(cities)
                self.param_sliders['cities'].set_current_value(len(cities))
                print(f"Loaded {len(cities)} cities from {file_path}")
                
                self.paused = True
    
    def save_cities_dialog(self):
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        file_path = filedialog.asksaveasfilename(
            title="Save Cities",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")],
            defaultextension=".txt"
        )
        
        if file_path:
            success = save_cities_to_file(self.cities, file_path)
            if success:
                print(f"Saved {len(self.cities)} cities to {file_path}")
            else:
                print("Failed to save cities")
    
    def run_to_target(self):
        if self.n_cities < 2:
            return
            
        target = int(self.target_iter_slider.get_current_value())
        current = self.aco.current_iteration
        
        if current >= target:
            return
            
        self.running_to_target = True
        self.paused = False
        self.manual_mode = False

    def draw_city_labels(self, full_labels=False):
        
        for i, city in enumerate(self.cities):
            if isinstance(city, dict):
                x, y = city['x'], city['y']
                name = city.get('name', str(i))
                if 'country' in city:
                    name += f", {city['country']}"
            else:
                x, y = city
                name = str(i)
                
            if not full_labels:
                name = str(i) if isinstance(city, dict) else str(i)
            
            name_label = self.font.render(name, True, TEXT_COLOR)
            self.screen.blit(name_label, (x + 10, y - 10))

    def save_visualization_as_image(self, filename):
        image_surface = self.screen.copy()
        
        image_surface.fill(BG_COLOR)
        
        panel_rect = pygame.Rect(self.width - 280, 0, 280, self.height)
        pygame.draw.rect(image_surface, (220, 220, 220), panel_rect)
        
        large_font = pygame.font.SysFont(None, FONT_SIZE + 8)
        for i, city in enumerate(self.cities):
            if isinstance(city, dict):
                x, y = city['x'], city['y']
                name = city.get('name', f"City {i+1}")
            else:
                x, y = city
                name = f"City {i+1}"
                
            pygame.draw.circle(image_surface, CITY_COLOR, (x, y), 10)
            
            name_label = large_font.render(name, True, (0, 0, 0))
            label_bg = pygame.Rect(x + 12, y - 12, name_label.get_width() + 4, name_label.get_height() + 4)
            pygame.draw.rect(image_surface, (255, 255, 255, 180), label_bg)
            image_surface.blit(name_label, (x + 14, y - 10))
        
        # Draw only the best path
        best_path = self.aco.get_best_path()
        if best_path:
            points = []
            for city_idx in best_path:
                city = self.cities[city_idx]
                if isinstance(city, dict):
                    points.append((city['x'], city['y']))
                else:
                    points.append(city)
            
            # Draw with thicker line for visibility
            pygame.draw.lines(image_surface, (0, 0, 0), True, points, 3)
        
        # Add information footer
        info_font = pygame.font.SysFont(None, FONT_SIZE + 4)
        distance_unit = 'km' if self.aco.is_geo else 'units'
        info_texts = [
            f"Best Path Length: {self.aco.get_best_path_length():.2f} {distance_unit}",
            f"Cities: {self.n_cities} | Iterations: {self.aco.current_iteration}",
            f"Algorithm: Ant Colony Optimization | Date: {time.strftime('%Y-%m-%d %H:%M')}",
            f"Mode: {'Geographic' if self.aco.is_geo else 'Euclidean'} coordinates"
        ]
        
        # Create footer background
        footer_height = len(info_texts) * 25 + 20
        footer_rect = pygame.Rect(0, self.height - footer_height, self.width, footer_height)
        footer_surface = pygame.Surface((footer_rect.width, footer_rect.height), pygame.SRCALPHA)
        footer_surface.fill((240, 240, 240, 230))
        image_surface.blit(footer_surface, footer_rect)
        
        y_pos = self.height - footer_height + 10
        for text in info_texts:
            text_surf = info_font.render(text, True, (0, 0, 0))
            image_surface.blit(text_surf, (20, y_pos))
            y_pos += 25
        
        pygame.image.save(image_surface, filename)
        print(f"Visualization saved as {filename}")
        return True

def load_cities_from_file(filename):
    try:
        # Determine file type by extension
        _, ext = os.path.splitext(filename)
        ext = ext.lower()  # <-- Fixed: changed from "lower()" to "ext.lower()"
        
        if ext == '.json':
            return load_from_json(filename)
        else:  # Default to CSV format for .csv, .txt, or any other extension
            return load_from_csv(filename)
    except Exception as e:
        print(f"Error loading cities from file: {e}")
        import traceback
        traceback.print_exc()  # Added stack trace for better debugging
        return None

def load_from_csv(filename):
    try:
        # Use pandas to read CSV properly
        df = pd.read_csv(filename)
        
        print(f"File: {filename}")
        print(f"Columns found: {list(df.columns)}")
        
        # Identify which columns contain city, lat and lng data
        city_col = None
        country_col = None
        lat_col = None
        lng_col = None
        
        # Prioritize location > city > country for name column
        # First pass: Look specifically for location column
        for col in df.columns:
            col_lower = col.lower()
            if col_lower == 'location':
                city_col = col
                print(f"Using as primary location column: {col}")
                break
        
        # Second pass: If no location column found, look for city column
        if city_col is None:
            for col in df.columns:
                col_lower = col.lower()
                if col_lower == 'city' or col_lower.startswith('city'):
                    city_col = col
                    print(f"Using as city column: {col}")
                    break
        
        # Third pass: Look for other name-related columns if still not found
        if city_col is None:
            for col in df.columns:
                col_lower = col.lower()
                if col_lower == 'name':
                    city_col = col
                    print(f"Using as name column: {col}")
                    break
        
        # Find country column
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ['country', 'nation'] or col_lower == 'countries':
                country_col = col
                print(f"Using as country column: {col}")
                break
                
        # Find latitude column
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ['lat', 'latitude']:
                lat_col = col
                print(f"Using as latitude column: {col}")
                break
                
        # Find longitude column
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ['lon', 'lng', 'long', 'longitude']:
                lng_col = col
                print(f"Using as longitude column: {col}")
                break
        
        # If we couldn't find the expected columns, try to use positional columns
        if not (lat_col and lng_col):
            print("Could not identify lat/lng columns by name, trying positional columns...")
            if len(df.columns) >= 3:
                # Assume format: city, latitude, longitude
                city_col = df.columns[0] if not city_col else city_col
                lat_col = df.columns[1]
                lng_col = df.columns[2]
                print(f"Using positional columns: City={city_col}, Lat={lat_col}, Lng={lng_col}")
        
        if not (lat_col and lng_col):
            print(f"Could not identify latitude and longitude columns.")
            print(f"Available columns: {list(df.columns)}")
            return None
        
        # Extract city data
        geo_cities = []
        for i, row in df.iterrows():
            try:
                if city_col:
                    name = str(row[city_col])
                else:
                    name = f"City {i+1}"
                    
                city_dict = {
                    'name': name,
                    'lat': float(row[lat_col]),
                    'lng': float(row[lng_col])
                }
                
                if country_col and pd.notna(row[country_col]):
                    city_dict['country'] = str(row[country_col])
                
                geo_cities.append(city_dict)
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse row {i+1}: {e}")
        
        print(f"Successfully parsed {len(geo_cities)} cities with geographic data")
        
        if geo_cities:
            scaled_cities = scale_geo_coords(geo_cities, SCREEN_WIDTH, SCREEN_HEIGHT)
            
            # Add after parsing the data but before returning
            if geo_cities:
                # Validate that coordinates are in reasonable ranges
                for city in geo_cities:
                    if abs(city['lat']) > 90 or abs(city['lng']) > 180:
                        print(f"WARNING: City {city['name']} has invalid coordinates: lat={city['lat']}, lng={city['lng']}")
                
                # Validate a few known distances
                for i in range(len(geo_cities)):
                    for j in range(i+1, len(geo_cities)):
                        city1 = geo_cities[i]
                        city2 = geo_cities[j]
                        if city1['name'] == 'London' and city2['name'] == 'Paris':
                            dist = haversine(city1['lng'], city1['lat'], city2['lng'], city2['lat'])
                            print(f"Validation: Distance from {city1['name']} to {city2['name']} is {dist:.2f} km")
                        elif city1['name'] == 'Paris' and city2['name'] == 'London':
                            dist = haversine(city1['lng'], city1['lat'], city2['lng'], city2['lat'])
                            print(f"Validation: Distance from {city1['name']} to {city2['name']} is {dist:.2f} km")
            
            return scaled_cities
        return []
    
    except Exception as e:
        print(f"Error loading from CSV: {e}")
        import traceback
        traceback.print_exc()
        return None

def load_from_json(filename):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Check if it's a geo format JSON
        is_geo_format = False
        geo_coords = []
        
        if isinstance(data, list) and len(data) > 0:
            sample = data[0]
            
            # Check for geo format attributes
            if isinstance(sample, dict):
                has_lat = any(key in sample for key in ['lat', 'latitude'])
                has_lng = any(key in sample for key in ['lng', 'long', 'longitude'])
                
                if has_lat and has_lng:
                    is_geo_format = True
                    
                    for item in data:
                        # Get latitude
                        lat = None
                        for key in ['lat', 'latitude']:
                            if key in item:
                                lat = float(item[key])
                                break
                        
                        # Get longitude
                        lng = None
                        for key in ['lng', 'long', 'longitude']:
                            if key in item:
                                lng = float(item[key])
                                break
                        
                        if lat is not None and lng is not None:
                            geo_coords.append((lng, lat))  # Geo format: (longitude, latitude)
                    
                    return scale_geo_coords(geo_coords, SCREEN_WIDTH, SCREEN_HEIGHT)
                else:
                    cities = []
                    for item in data:
                        if 'x' in item and 'y' in item:
                            cities.append((float(item['x']), float(item['y'])))
                    
                    if cities:
                        return cities
            
            cities = []
            for item in data:
                if isinstance(item, list) and len(item) >= 2:
                    cities.append((float(item[0]), float(item[1])))
            
            if cities:
                return cities
                
        return []
    except Exception as e:
        print(f"Error loading from JSON: {e}")
        return None

def save_cities_to_file(cities, filename):
    try:
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        if ext == '.json':
            with open(filename, 'w') as f:
                city_list = [{"x": x, "y": y} for x, y in cities]
                json.dump(city_list, f, indent=2)
        else:  # Default to CSV for .csv, .txt or any other extension
            with open(filename, 'w') as f:
                for x, y in cities:
                    f.write(f"{x},{y}\n")
        return True
    except Exception as e:
        print(f"Error saving cities to file: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ant Colony Optimization Visualization")
    parser.add_argument("--cities", type=int, default=20, help="Number of cities")
    parser.add_argument("--ants", type=int, default=20, help="Number of ants")
    parser.add_argument("--load", type=str, help="Load cities from file")
    parser.add_argument("--save", type=str, help="Save cities to file")
    
    args = parser.parse_args()
    
    visualizer = ACOVisualizer(n_cities=args.cities, n_ants=args.ants)
    
    if args.load:
        cities = load_cities_from_file(args.load)
        if cities:
            visualizer.cities = cities
            visualizer.n_cities = len(cities)
            visualizer.aco.update_coords(cities)
            visualizer.param_sliders['cities'].set_current_value(len(cities))
    
    visualizer.run()
    
    if args.save:
        save_cities_to_file(visualizer.cities, args.save)
