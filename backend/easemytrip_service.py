import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
import json
import time
import random

class EaseMyTripService:
    def __init__(self):
        """Initialize EaseMyTrip service"""
        self.api_key = "demo_key"
        self.base_url = "https://api.easemytrip.com"
    
    def get_bus_options(self, from_location: str, destination: str, departure_date: str) -> list:
        """Get enhanced bus options with realistic data"""
        import random
        
        # Realistic bus operators
        operators = [
            {"name": "KSRTC", "type": "government", "base_price": 400},
            {"name": "VRL Travels", "type": "private", "base_price": 800},
            {"name": "Orange Tours", "type": "private", "base_price": 700},
            {"name": "Neeta Travels", "type": "private", "base_price": 900},
            {"name": "SRS Travels", "type": "private", "base_price": 750},
            {"name": "KPN Travels", "type": "private", "base_price": 650}
        ]
        
        bus_types = ["Semi-Sleeper", "Sleeper", "AC Sleeper", "Non-AC", "AC Seater"]
        
        buses = []
        
        # Generate 4-6 realistic bus options
        for i in range(5):
            operator = operators[i % len(operators)]
            bus_type = random.choice(bus_types)
            
            # Calculate realistic pricing
            base_price = operator["base_price"]
            if "AC" in bus_type:
                base_price += 300
            if "Sleeper" in bus_type:
                base_price += 200
            
            # Add some variation
            price_variation = random.randint(-100, 200)
            final_price = max(300, base_price + price_variation)
            
            # Generate realistic times
            departure_hour = random.randint(6, 23)
            departure_minute = random.choice([0, 15, 30, 45])
            duration_hours = random.randint(4, 12)  # Bus journeys are longer
            duration_minutes = random.randint(0, 59)
            
            arrival_hour = (departure_hour + duration_hours) % 24
            arrival_minute = (departure_minute + duration_minutes) % 60
            
            bus = {
                "name": f"{operator['name']} {bus_type}",
                "type": "bus",
                "operator": operator["name"],
                "bus_type": bus_type,
                "departure_time": f"{departure_hour:02d}:{departure_minute:02d}",
                "arrival_time": f"{arrival_hour:02d}:{arrival_minute:02d}",
                "duration": f"{duration_hours}h {duration_minutes}m",
                "price": final_price,
                "currency": "INR",
                "seats_available": random.randint(5, 25),
                "amenities": self._get_bus_amenities(bus_type),
                "rating": round(random.uniform(3.5, 4.8), 1),
                "origin": from_location,
                "destination": destination,
                "departure_date": departure_date
            }
            
            buses.append(bus)
        
        return buses
    
    def get_train_options(self, from_location: str, destination: str, departure_date: str) -> list:
        """Get enhanced train options with realistic data"""
        import random
        
        # Realistic train classes and pricing
        train_classes = [
            {"name": "AC 1 Tier", "code": "1A", "base_price": 2500},
            {"name": "AC 2 Tier", "code": "2A", "base_price": 1800},
            {"name": "AC 3 Tier", "code": "3A", "base_price": 1200},
            {"name": "AC Chair Car", "code": "CC", "base_price": 800},
            {"name": "Sleeper", "code": "SL", "base_price": 500},
            {"name": "Second Sitting", "code": "2S", "base_price": 300}
        ]
        
        # Popular train numbers and names
        trains = [
            {"number": "12639", "name": "Bangalore Express"},
            {"number": "12627", "name": "Karnataka Express"},
            {"number": "12649", "name": "Shatabdi Express"},
            {"number": "12615", "name": "Grand Trunk Express"},
            {"number": "12677", "name": "Mysore Express"},
            {"number": "12647", "name": "Brindavan Express"}
        ]
        
        train_options = []
        
        # Generate 4-6 realistic train options
        for i in range(5):
            train = trains[i % len(trains)]
            train_class = random.choice(train_classes)
            
            # Calculate realistic pricing
            base_price = train_class["base_price"]
            price_variation = random.randint(-200, 300)
            final_price = max(200, base_price + price_variation)
            
            # Generate realistic times
            departure_hour = random.randint(5, 22)
            departure_minute = random.choice([0, 15, 30, 45])
            duration_hours = random.randint(3, 8)  # Train journeys vary
            duration_minutes = random.randint(0, 59)
            
            arrival_hour = (departure_hour + duration_hours) % 24
            arrival_minute = (departure_minute + duration_minutes) % 60
            
            train_option = {
                "name": f"{train['name']} ({train['number']})",
                "type": "train",
                "train_number": train["number"],
                "train_name": train["name"],
                "class": train_class["name"],
                "class_code": train_class["code"],
                "departure_time": f"{departure_hour:02d}:{departure_minute:02d}",
                "arrival_time": f"{arrival_hour:02d}:{arrival_minute:02d}",
                "duration": f"{duration_hours}h {duration_minutes}m",
                "price": final_price,
                "currency": "INR",
                "seats_available": random.randint(10, 50),
                "amenities": self._get_train_amenities(train_class["name"]),
                "rating": round(random.uniform(3.8, 4.9), 1),
                "origin": from_location,
                "destination": destination,
                "departure_date": departure_date
            }
            
            train_options.append(train_option)
        
        return train_options
    
    def _get_bus_amenities(self, bus_type: str) -> list:
        """Get amenities based on bus type"""
        amenities = ["Water Bottle", "Blanket"]
        
        if "AC" in bus_type:
            amenities.extend(["AC", "Charging Point"])
        if "Sleeper" in bus_type:
            amenities.extend(["Sleeper Berth", "Pillow"])
        if "Semi-Sleeper" in bus_type:
            amenities.extend(["Reclining Seats", "Footrest"])
        
        return amenities
    
    def _get_train_amenities(self, train_class: str) -> list:
        """Get amenities based on train class"""
        amenities = ["Water Bottle"]
        
        if "AC" in train_class:
            amenities.extend(["AC", "Bedding", "Charging Point"])
        if "1 Tier" in train_class:
            amenities.extend(["Private Cabin", "Meals", "WiFi"])
        elif "2 Tier" in train_class:
            amenities.extend(["Curtains", "Meals"])
        elif "3 Tier" in train_class:
            amenities.extend(["Curtains"])
        elif "Chair Car" in train_class:
            amenities.extend(["AC", "Reclining Seats"])
        elif "Sleeper" in train_class:
            amenities.extend(["Bedding"])
        
        return amenities
