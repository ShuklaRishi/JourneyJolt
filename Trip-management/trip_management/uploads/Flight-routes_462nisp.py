from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Airport, Flight

class RouteViewSet(viewsets.ViewSet):
    def list(self, request):
        source_code = request.GET.get('source_code')
        destination_code = request.GET.get('destination_code')

        try:
            source_airport = Airport.objects.get(code=source_code)
            destination_airport = Airport.objects.get(code=destination_code)

            direct_flights = Flight.objects.filter(
                departure_airport=source_airport,
                arrival_airport=destination_airport
            )

            if direct_flights.exists():
                # Direct flight available
                route = direct_flights.first()
                route_data = {
                    'source': source_airport.name,
                    'destination': destination_airport.name,
                    'flights': [
                        {
                            'departure_airport': route.departure_airport.name,
                            'arrival_airport': route.arrival_airport.name,
                            'departure_time': route.departure_time,
                            'arrival_time': route.arrival_time
                        }
                    ]
                }
            else:
                # Find connecting flights via intermediate airport
                intermediate_airports = Airport.objects.exclude(code__in=[source_code, destination_code])
                connecting_flights = Flight.objects.filter(
                    departure_airport=source_airport,
                    arrival_airport__in=intermediate_airports
                )

                if connecting_flights.exists():
                    route_data = {
                        'source': source_airport.name,
                        'destination': destination_airport.name,
                        'flights': []
                    }

                    for flight in connecting_flights:
                        intermediate_airport = flight.arrival_airport
                        intermediate_flights = Flight.objects.filter(
                            departure_airport=intermediate_airport,
                            arrival_airport=destination_airport
                        )

                        if intermediate_flights.exists():
                            intermediate_flight = intermediate_flights.first()
                            route_data['flights'].append(
                                {
                                    'departure_airport': flight.departure_airport.name,
                                    'arrival_airport': intermediate_airport.name,
                                    'departure_time': flight.departure_time,
                                    'arrival_time': flight.arrival_time
                                }
                            )
                            route_data['flights'].append(
                                {
                                    'departure_airport': intermediate_airport.name,
                                    'arrival_airport': intermediate_flight.arrival_airport.name,
                                    'departure_time': intermediate_flight.departure_time,
                                    'arrival_time': intermediate_flight.arrival_time
                                }
                            )

                    if len(route_data['flights']) > 0:
                        route_data['flights'].append(
                            {
                                'departure_airport': intermediate_flight.arrival_airport.name,
                                'arrival_airport': intermediate_flight.arrival_airport.name,
                                'departure_time': intermediate_flight.arrival_time,
                                'arrival_time': intermediate_flight.arrival_time
                            }
                        )
                else:
                    # No connecting flights available
                    route_data = {
                        'message': 'No flights available for the given route.'
                    }

            return Response(route_data, status=status.HTTP_200_OK)

        except Airport.DoesNotExist:
            return Response({'message': 'Invalid airport code.'}, status=status.HTTP_400_BAD_REQUEST)

