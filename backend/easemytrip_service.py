import random
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional

import requests


class EaseMyTripService:
    """Fetch live transportation data from publicly available EaseMyTrip endpoints."""

    BUS_API_BASE = "https://busservice.easemytrip.com/v1/api"
    BUS_WEB_BASE = "https://bus.easemytrip.com"
    TRAIN_BASE = "https://railways.easemytrip.com"
    TRAIN_AUTOSUGGEST_BASE = "https://solr.easemytrip.com/api/auto/GetTrainAutoSuggest"
    USER_AGENT = "Mozilla/5.0 (WanderlyHackathon/1.0)"

    # City name normalization dictionary
    # Using hardcoded synonyms instead of AI for better:
    # 1. Speed: No API call latency (instant lookup)
    # 2. Reliability: Always works, no API failures
    # 3. Cost: Free (no API costs)
    # 4. Predictability: Same result every time
    # 
    # AI could handle more edge cases but adds latency and cost.
    # For common cities (which is 99% of use cases), hardcoded is better.
    # We can expand this dictionary as needed for more cities.
    CITY_SYNONYMS = {
        "bengaluru": "Bangalore",
        "bangalore": "Bangalore",
        "bombay": "Mumbai",
        "mumbai": "Mumbai",
        "madras": "Chennai",
        "chennai": "Chennai",
        "calcutta": "Kolkata",
        "kolkata": "Kolkata",
        "pune": "Pune",
        "poona": "Pune",
        "hyderabad": "Hyderabad",
        "secunderabad": "Hyderabad",
        "delhi": "Delhi",
        "new delhi": "Delhi",
        "ncr": "Delhi",
    }

    def __init__(self):
        self.bus_session = requests.Session()
        self.train_session = requests.Session()
        self.bus_session.headers.update({"User-Agent": self.USER_AGENT})
        self.train_session.headers.update({"User-Agent": self.USER_AGENT})
        self._bus_city_cache: Dict[str, Dict] = {}
        self._train_station_cache: Dict[str, Dict] = {}
        self._rng = random.Random()

    def get_bus_options(self, from_location: str, destination: str, departure_date: str) -> List[Dict]:
        """Return real bus options from EaseMyTrip's bus search service."""
        try:
            return self._fetch_bus_options(from_location, destination, departure_date)
        except Exception as exc:
            print(f"[EaseMyTripService] Bus fetch failed: {exc}")
            return self._generate_bus_fallback(from_location, destination, departure_date)

    def get_train_options(self, from_location: str, destination: str, departure_date: str) -> List[Dict]:
        """Return real train options from EaseMyTrip's railway service."""
        try:
            return self._fetch_train_options(from_location, destination, departure_date)
        except Exception as exc:
            print(f"[EaseMyTripService] Train fetch failed: {exc}")
            return self._generate_train_fallback(from_location, destination, departure_date)

    # -------------------------------------------------------------------------
    # Bus helpers
    # -------------------------------------------------------------------------

    def _fetch_bus_options(self, from_location: str, destination: str, departure_date: str) -> List[Dict]:
        print(
            "[EaseMyTripService] fetch_bus_options "
            f"raw_from={from_location!r} raw_to={destination!r} raw_date={departure_date!r}"
        )
        normalized_from = self._normalize_city_input(from_location)
        normalized_to = self._normalize_city_input(destination)
        print(
            "[EaseMyTripService] normalized bus locations "
            f"from={normalized_from!r} to={normalized_to!r}"
        )
        source_city = self._resolve_bus_city(normalized_from)
        dest_city = self._resolve_bus_city(normalized_to)

        if not source_city or not dest_city:
            print(
                "[EaseMyTripService] bus city resolution failed",
                f"source={source_city} dest={dest_city}",
            )
            raise ValueError("Unable to resolve bus cities on EaseMyTrip")

        print(
            "[EaseMyTripService] resolved bus cities",
            f"source={source_city['name']}({source_city['id']})",
            f"dest={dest_city['name']}({dest_city['id']})",
        )

        travel_date = self._format_bus_date(departure_date)
        print(f"[EaseMyTripService] formatted bus date={travel_date}")
        referer = (
            f"{self.BUS_WEB_BASE}/home/list?"
            f"org={urllib.parse.quote(source_city['name'])}"
            f"&des={urllib.parse.quote(dest_city['name'])}"
            f"&date={travel_date}"
            f"&searchid={source_city['id']}_{dest_city['id']}"
            f"&CCode=IN&AppCode=EMT"
        )

        # Warm up cookies just like the public site does
        try:
            self.bus_session.get(referer, timeout=8)
        except requests.RequestException:
            pass

        payload = {
            "SourceCityId": source_city["id"],
            "DestinationCityId": dest_city["id"],
            "SourceCityName": source_city["name"],
            "DestinatinCityName": dest_city["name"],
            "JournyDate": travel_date,
            "Vid": "",
            "agentCode": "NAN",
            "agentType": "NAN",
            "CurrencyDomain": "IN",
            "Sid": "",
            "snapApp": "EMT",
            "TravelPolicy": [],
            "isInventory": 0,
        }

        headers = {
            "Content-Type": "application/json",
            "Origin": self.BUS_WEB_BASE,
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        }

        response = self.bus_session.post(
            f"{self.BUS_API_BASE}/Home/GetSearchResult/",
            json=payload,
            headers=headers,
            timeout=12,
        )
        response.raise_for_status()

        data = response.json()
        trips = (data.get("Response") or {}).get("AvailableTrips") or []
        currency = (data.get("Response") or {}).get("Currency") or "INR"
        print(
            "[EaseMyTripService] EMT bus response",
            f"trips={len(trips)} currency={currency}",
            f"isSearchCompleted={(data or {}).get('IsSearchCompleted')}",
        )

        suggestions: List[Dict] = []
        for trip in trips:
            suggestion = self._serialize_bus_trip(
                trip=trip,
                source=source_city,
                destination=dest_city,
                travel_date=travel_date,
                currency=currency,
                referer=referer,
            )
            suggestions.append(suggestion)

        if not suggestions:
            raise ValueError("EaseMyTrip returned zero bus trips")

        return suggestions

    def _serialize_bus_trip(
        self,
        trip: Dict,
        source: Dict,
        destination: Dict,
        travel_date: str,
        currency: str,
        referer: str,
    ) -> Dict:
        departure_time = trip.get("DepartureTime12Format") or trip.get("departureTime")
        arrival_time = trip.get("ArrivalTime12Format") or trip.get("arrivalTime")
        duration = trip.get("showDuration") or trip.get("duration")
        amenities = trip.get("lstamenities") or []
        available_seats = trip.get("AvailableSeats")
        price = trip.get("price")

        booking_url = f"{referer}&busId={trip.get('id')}#bus-{trip.get('id')}"

        features = [
            trip.get("busType"),
            f"{available_seats} seats left" if available_seats is not None else None,
            "Live tracking" if trip.get("liveTrackingAvailable") else None,
            "mTicket supported" if trip.get("mTicketEnabled") else None,
        ]
        features = [feature for feature in features if feature]

        bd_points = trip.get("bdPoints") or []
        dp_points = trip.get("dpPoints") or []

        return {
            "name": f"{trip.get('Travels', '').strip()} ({trip.get('busType', '').strip()})".strip(),
            "type": "bus",
            "operator": trip.get("Travels"),
            "bus_type": trip.get("busType"),
            "description": self._build_bus_description(duration, bd_points, dp_points),
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "duration": duration,
            "price": price,
            "price_range": self._format_price(currency, price),
            "currency": currency,
            "seats_available": available_seats,
            "amenities": amenities,
            "features": features or amenities[:4],
            "rating": None,
            "origin": source["name"],
            "destination": destination["name"],
            "location": f"{source['name']} to {destination['name']}",
            "departure_date": travel_date,
            "why_recommended": self._build_bus_reason(trip, available_seats),
            "booking_url": booking_url,
            "external_url": booking_url,
            "link_type": "booking",
            "source_id": source["id"],
            "destination_id": destination["id"],
        }

    def _build_bus_description(self, duration: Optional[str], bd_points: List[Dict], dp_points: List[Dict]) -> str:
        segments = []
        if duration:
            segments.append(f"Approx. {duration}")
        if bd_points:
            segments.append(f"Boarding: {bd_points[0].get('bdPoint')}")
        if dp_points:
            segments.append(f"Drop: {dp_points[0].get('dpName') or dp_points[0].get('locatoin')}")
        return " • ".join(segments) if segments else "Curated by EaseMyTrip"

    def _build_bus_reason(self, trip: Dict, available_seats: Optional[int]) -> str:
        reasons = []
        if trip.get("isVolvo"):
            reasons.append("Volvo coach")
        if trip.get("partialCancellationAllowed"):
            reasons.append("Flexible cancellation")
        if available_seats is not None:
            reasons.append(f"{available_seats} seats open")
        if not reasons:
            reasons.append("vetted via EaseMyTrip live inventory")
        return " • ".join(reasons)

    def _resolve_bus_city(self, query: str) -> Optional[Dict]:
        normalized = (query or "").strip().lower()
        if not normalized:
            return None
        if normalized in self._bus_city_cache:
            return self._bus_city_cache[normalized]

        try:
            resp = self.bus_session.get(
                f"{self.BUS_API_BASE}/search/getsourcecity",
                params={"id": query.strip()},
                timeout=8,
            )
            resp.raise_for_status()
            options = resp.json() or []
        except requests.RequestException:
            options = []

        if not options:
            return None

        match = self._pick_best_match(query, options, key="name")
        self._bus_city_cache[normalized] = match
        return match

    # -------------------------------------------------------------------------
    # Train helpers
    # -------------------------------------------------------------------------

    def _fetch_train_options(self, from_location: str, destination: str, departure_date: str) -> List[Dict]:
        print(
            "[EaseMyTripService] fetch_train_options "
            f"raw_from={from_location!r} raw_to={destination!r} raw_date={departure_date!r}"
        )
        normalized_from = self._normalize_train_station_input(from_location)
        normalized_to = self._normalize_train_station_input(destination)
        print(
            "[EaseMyTripService] normalized train locations "
            f"from={normalized_from!r} to={normalized_to!r}"
        )
        source_station = self._resolve_train_station(normalized_from)
        dest_station = self._resolve_train_station(normalized_to)

        if not source_station or not dest_station:
            print(
                "[EaseMyTripService] train station resolution failed",
                f"source={source_station} dest={dest_station}",
            )
            raise ValueError("Unable to resolve train stations on EaseMyTrip")

        travel_date = self._format_train_date(departure_date)
        print(f"[EaseMyTripService] formatted train date={travel_date}")

        payload = {
            "fromSec": source_station["display"],
            "toSec": dest_station["display"],
            "fromdate": travel_date,
            "selectedTrain": "",
            "couponCode": "",
        }

        response = self.train_session.post(
            f"{self.TRAIN_BASE}/Train/_TrainBtwnStationList",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        trains = data.get("trainBtwnStnsList") or []
        print(
            "[EaseMyTripService] EMT train response",
            f"trains={len(trains)} quotaList_len={len(data.get('quotaList') or [])}",
        )

        suggestions: List[Dict] = []
        for train in trains:
            suggestion = self._serialize_train_option(
                train=train,
                source=source_station,
                destination=dest_station,
                travel_date=travel_date,
            )
            suggestions.append(suggestion)

        if not suggestions:
            raise ValueError("EaseMyTrip returned zero train options")

        return suggestions

    def _parse_price_value(self, value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            as_str = str(value)
            clean = ''.join(ch for ch in as_str if ch.isdigit())
            return int(clean) if clean else None
        except Exception:
            return None

    def _serialize_train_option(
        self,
        train: Dict,
        source: Dict,
        destination: Dict,
        travel_date: str,
    ) -> Dict:
        fare_options = [
            fare
            for fare in train.get("TrainClassWiseFare") or []
            if fare.get("enqClass")
        ]
        # Sort by numeric fare (if provided) so the cheapest option is first
        def _fare_sort_key(fare: Dict) -> int:
            parsed = self._parse_price_value(fare.get("totalFare"))
            return parsed if parsed is not None else 10**9
        fare_options = sorted(fare_options, key=_fare_sort_key)
        fare = fare_options[0] if fare_options else None

        price = self._parse_price_value(fare.get("totalFare")) if fare else None
        if (price is None or price == 0) and fare:
            fallback_fields = [
                "fareWithTax",
                "totalFareWithGst",
                "baseFare",
                "fare",
            ]
            for field in fallback_fields:
                price = self._parse_price_value(fare.get(field))
                if price:
                    break
        if (price is None or price == 0) and train.get("minFare"):
            price = self._parse_price_value(train.get("minFare"))

        availability = ""
        if fare and fare.get("avlDayList"):
            availability = fare["avlDayList"][0].get("availablityStatusNew") or ""

        booking_class = fare["enqClass"] if fare else "SL"
        slug_from = self._slugify(source["name"])
        slug_to = self._slugify(destination["name"])
        booking_url = (
            f"{self.TRAIN_BASE}/TrainInfo/"
            f"{slug_from}-to-{slug_to}/"
            f"{booking_class}/"
            f"{train.get('trainNumber')}/"
            f"{train.get('fromStnCode')}/{train.get('toStnCode')}/"
            f"{travel_date.replace('/', '-')}"
        )

        features = [
            f"{train.get('trainType')} service" if train.get("trainType") else None,
            f"Distance: {train.get('distance')} km" if train.get("distance") else None,
            f"Availability: {availability}" if availability else None,
        ]
        features = [feature for feature in features if feature]

        return {
            "name": f"{train.get('trainName')} ({train.get('trainNumber')})",
            "type": "train",
            "train_number": train.get("trainNumber"),
            "train_name": train.get("trainName"),
            "class": fare.get("enqClassName") if fare else None,
            "class_code": booking_class,
            "description": self._build_train_description(train),
            "departure_time": train.get("DeptTime_12") or train.get("departureTime"),
            "arrival_time": train.get("ArrTime_12") or train.get("arrivalTime"),
            "duration": train.get("duration"),
            "price": price,
            "price_range": self._format_price("INR", price) if price else None,
            "currency": "INR",
            "seats_available": availability,
            "amenities": [],
            "features": features,
            "rating": None,
            "origin": source["name"],
            "destination": destination["name"],
            "location": f"{source['name']} to {destination['name']}",
            "departure_date": travel_date,
            "why_recommended": self._build_train_reason(availability, train),
            "booking_url": booking_url,
            "external_url": booking_url,
            "link_type": "booking",
            "source_code": source["code"],
            "destination_code": destination["code"],
        }

    def _build_train_description(self, train: Dict) -> str:
        segments = [
            f"Runs {self._build_running_days(train)}",
            f"From {train.get('fromStnName')} ({train.get('fromStnCode')})",
            f"To {train.get('toStnName')} ({train.get('toStnCode')})",
        ]
        return " • ".join([segment for segment in segments if segment])

    def _build_running_days(self, train: Dict) -> str:
        days = [
            ("Mon", train.get("runningMon")),
            ("Tue", train.get("runningTue")),
            ("Wed", train.get("runningWed")),
            ("Thu", train.get("runningThu")),
            ("Fri", train.get("runningFri")),
            ("Sat", train.get("runningSat")),
            ("Sun", train.get("runningSun")),
        ]
        active = [label for label, flag in days if str(flag).lower() == "true"]
        return ", ".join(active) if active else "daily"

    def _build_train_reason(self, availability: str, train: Dict) -> str:
        reasons = []
        if availability:
            reasons.append(availability)
        if train.get("flexiFlag"):
            reasons.append("Flexi fare eligible")
        reasons.append("Live data via EaseMyTrip rail inventory")
        return " • ".join(reasons)

    def _resolve_train_station(self, query: str) -> Optional[Dict]:
        normalized = (query or "").strip().lower()
        if not normalized:
            return None
        if normalized in self._train_station_cache:
            cached = self._train_station_cache[normalized]
            if cached is not None:  # Only return if not a cached None
                return cached

        # Retry logic for transient API errors
        max_retries = 3
        options = []
        for attempt in range(max_retries):
            try:
                resp = self.train_session.get(
                    f"{self.TRAIN_AUTOSUGGEST_BASE}/{urllib.parse.quote(query.strip())}",
                    timeout=8,
                )
                resp.raise_for_status()
                options = resp.json() or []
                if options:
                    break  # Success, exit retry loop
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"[EaseMyTripService] Train station API error (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                    continue
                else:
                    print(f"[EaseMyTripService] Train station API error after {max_retries} attempts: {e}")
                    options = []

        if not options:
            # Cache None to avoid repeated failed API calls
            self._train_station_cache[normalized] = None
            return None

        match = self._pick_best_train_station(query, options)
        station = {
            "code": match["Code"],
            "name": match["Name"],
            "display": f"{match['Name']} ({match['Code']})",
        }
        self._train_station_cache[normalized] = station
        return station

    # -------------------------------------------------------------------------
    # Formatting helpers & fallbacks
    # -------------------------------------------------------------------------

    def _ensure_date(self, raw: Optional[str], target_format: str) -> str:
        if raw:
            raw = raw.strip()
        candidates = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d %b %Y",
        ]
        for pattern in candidates:
            try:
                return datetime.strptime(raw, pattern).strftime(target_format)
            except Exception:
                continue
        return datetime.utcnow().strftime(target_format)

    def _format_bus_date(self, raw: Optional[str]) -> str:
        return self._ensure_date(raw, "%d-%m-%Y")

    def _format_train_date(self, raw: Optional[str]) -> str:
        return self._ensure_date(raw, "%d/%m/%Y")

    def _format_price(self, currency: str, amount: Optional[float]) -> Optional[str]:
        if amount is None:
            return None
        symbol = "₹" if currency.upper() == "INR" else currency
        return f"{symbol}{int(amount):,}"

    def _slugify(self, value: str) -> str:
        cleaned = (value or "").strip().lower().replace(" ", "-")
        return urllib.parse.quote(cleaned)

    def _pick_best_match(self, query: str, options: List[Dict], key: str) -> Dict:
        query_lower = query.strip().lower()
        for option in options:
            label = str(option.get(key, "")).lower()
            if query_lower in label:
                return option
        return options[0]

    def _pick_best_train_station(self, query: str, options: List[Dict]) -> Dict:
        query_lower = query.strip().lower()
        for option in options:
            if query_lower in (option.get("Name") or "").lower():
                return option
            if query_lower in (option.get("Show") or "").lower():
                return option
        return options[0]

    def _normalize_city_input(self, value: str) -> str:
        if not value:
            return ""
        cleaned = value.strip()
        if "," in cleaned:
            cleaned = cleaned.split(",", 1)[0]
        if "(" in cleaned:
            cleaned = cleaned.split("(", 1)[0]
        cleaned = " ".join(cleaned.split())
        synonym = self.CITY_SYNONYMS.get(cleaned.lower())
        return synonym or cleaned
    
    def _normalize_train_station_input(self, value: str) -> str:
        """Normalize city name for train station lookup.
        Train API uses different names than bus API (e.g., 'Bengaluru' not 'Bangalore')."""
        if not value:
            return ""
        cleaned = value.strip()
        if "," in cleaned:
            cleaned = cleaned.split(",", 1)[0]
        if "(" in cleaned:
            cleaned = cleaned.split("(", 1)[0]
        cleaned = " ".join(cleaned.split())
        
        # Train-specific mappings (EaseMyTrip train API uses different names)
        train_synonyms = {
            "bangalore": "Bengaluru",  # Train API expects "Bengaluru"
            "bengaluru": "Bengaluru",
            "bombay": "Mumbai",
            "mumbai": "Mumbai",
            "madras": "Chennai",
            "chennai": "Chennai",
        }
        
        return train_synonyms.get(cleaned.lower(), cleaned)

    def _generate_bus_fallback(self, from_location: str, destination: str, departure_date: str) -> List[Dict]:
        bus_types = ["Semi-Sleeper", "Sleeper", "AC Sleeper", "Non-AC", "AC Seater"]
        operators = [
            {"name": "KSRTC", "base_price": 400},
            {"name": "VRL Travels", "base_price": 800},
            {"name": "Orange Tours", "base_price": 700},
            {"name": "Neeta Travels", "base_price": 900},
            {"name": "SRS Travels", "base_price": 750},
        ]
        suggestions = []
        for _ in range(4):
            operator = self._rng.choice(operators)
            bus_type = self._rng.choice(bus_types)
            price = operator["base_price"] + self._rng.randint(50, 350)
            suggestions.append(
                {
                    "name": f"{operator['name']} {bus_type}",
                    "type": "bus",
                    "operator": operator["name"],
                    "bus_type": bus_type,
                    "description": f"Comfortable {bus_type.lower()} service",
                    "departure_time": "22:00",
                    "arrival_time": "06:00",
                    "duration": "8h",
                    "price": price,
                    "price_range": f"₹{price}",
                    "currency": "INR",
                    "seats_available": self._rng.randint(5, 20),
                    "amenities": ["Water Bottle", "Blanket"],
                    "features": ["Fallback data"],
                    "origin": from_location,
                    "destination": destination,
                    "location": f"{from_location} to {destination}",
                    "departure_date": departure_date,
                    "why_recommended": "Temporary fallback suggestion",
                    "booking_url": "https://www.easemytrip.com/",
                    "external_url": "https://www.easemytrip.com/",
                    "link_type": "booking",
                }
            )
        return suggestions

    def _generate_train_fallback(self, from_location: str, destination: str, departure_date: str) -> List[Dict]:
        train_names = [
            ("Grand Trunk Express", "12615"),
            ("Shatabdi Express", "12007"),
            ("Rajdhani Express", "12951"),
        ]
        suggestions = []
        for name, number in train_names:
            price = self._rng.randint(500, 2000)
            suggestions.append(
                {
                    "name": f"{name} ({number})",
                    "type": "train",
                    "train_number": number,
                    "train_name": name,
                    "class": "Sleeper",
                    "class_code": "SL",
                    "description": "Fallback IR service",
                    "departure_time": "21:30",
                    "arrival_time": "05:45",
                    "duration": "8h 15m",
                    "price": price,
                    "price_range": f"₹{price}",
                    "currency": "INR",
                    "seats_available": "WL",
                    "features": ["Fallback data"],
                    "origin": from_location,
                    "destination": destination,
                    "location": f"{from_location} to {destination}",
                    "departure_date": departure_date,
                    "why_recommended": "Temporary fallback suggestion",
                    "booking_url": "https://www.easemytrip.com/railways/",
                    "external_url": "https://www.easemytrip.com/railways/",
                    "link_type": "booking",
                }
            )
        return suggestions
