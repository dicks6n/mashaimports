"""Deep links to hotel booking sites, with your affiliate ids attached.

Set the ids in .env:
    TRIP_ALLIANCE_ID / TRIP_SID  — from the Trip.com Affiliate dashboard
    BOOKING_AID                  — from the Booking.com Affiliate Partner Programme
"""

from datetime import date, timedelta
from urllib.parse import urlencode

from django.conf import settings


def default_dates():
    checkin = date.today() + timedelta(days=14)
    return checkin, checkin + timedelta(days=3)


def _query(hotel_or_city):
    if hasattr(hotel_or_city, "city"):  # a Hotel
        return f"{hotel_or_city.display_name}, {hotel_or_city.city.name}"
    return f"{hotel_or_city.name}, China"


def trip_url(target, checkin, checkout, guests=1):
    city = getattr(target, "city", target)
    params = {
        "checkin": checkin.strftime("%Y/%m/%d"),
        "checkout": checkout.strftime("%Y/%m/%d"),
        "adult": guests,
        "crn": 1,
    }
    if city.trip_city_id:
        params["city"] = city.trip_city_id
    params["keyword"] = _query(target) if hasattr(target, "city") else city.name
    if settings.TRIP_ALLIANCE_ID:
        params["Allianceid"] = settings.TRIP_ALLIANCE_ID
        params["SID"] = settings.TRIP_SID
    return "https://www.trip.com/hotels/list?" + urlencode(params)


def booking_url(target, checkin, checkout, guests=1):
    params = {
        "ss": _query(target),
        "checkin": checkin.isoformat(),
        "checkout": checkout.isoformat(),
        "group_adults": guests,
        "no_rooms": 1,
    }
    if settings.BOOKING_AID:
        params["aid"] = settings.BOOKING_AID
    return "https://www.booking.com/searchresults.html?" + urlencode(params)


def links_for(target, checkin, checkout, guests=1):
    return {
        "trip": trip_url(target, checkin, checkout, guests),
        "booking": booking_url(target, checkin, checkout, guests),
    }
