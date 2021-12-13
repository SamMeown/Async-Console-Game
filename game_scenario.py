PHRASES = {
    1957: "First Sputnik",
    1961: "Gagarin flew!",
    1969: "Armstrong got on the moon!",
    1971: "First orbital space station Salute-1",
    1981: "Flight of the Shuttle Columbia",
    1998: 'ISS start building',
    2011: 'Messenger launch to Mercury',
    2021: 'Russia tests anti-satellite weapon, now tons of garbage',
}


def get_garbage_delay_tics(year):
    if year < 1961:
        return None
    elif year < 1969:
        return 20
    elif year < 1981:
        return 18
    elif year < 1995:
        return 16
    elif year < 2010:
        return 14
    elif year < 2021:
        return 12
    elif year < 2025:
        return 10
    else:
        return 8
