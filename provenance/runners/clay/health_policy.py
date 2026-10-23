"""Clay-only policy: preserve empty historical pools and record their skew warning."""
def acceptable_health(status):
    health=status['health']
    if health['status']=='HEALTH_OK':return not health.get('checks')
    checks=health.get('checks',{})
    return (health['status']=='HEALTH_WARN' and set(checks)=={'MANY_OBJECTS_PER_PG'}
            and checks['MANY_OBJECTS_PER_PG']['severity']=='HEALTH_WARN')
