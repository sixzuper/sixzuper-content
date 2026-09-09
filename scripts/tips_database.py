#!/usr/bin/env python3
"""
SixZuper Tech Tips Database
Database of daily tech tips for IG auto-posting.
"""

TIPS = [
    # Laravel / PHP
    "Gunakan Queue Worker untuk task yang lambat — jangan blokir request!",
    "Cache hasil query database, jangan query berulang kali.",
    "Pakai .env untuk semua konfigurasi — jangan hardcoded values.",
    "Database indexing wajib — tanpa index, query jadi lambat.",
    "Rate limiting mencegah abuse — gunakan Redis + token bucket.",
    "Error handling yang baik = logging + alert + graceful degradation.",
    "Use prepared statements untuk cegah SQL injection.",
    
    # Architecture / DevOps
    "Gunakan CDN untuk static assets — lebih cepat & hemat bandwidth.",
    "Containerize apps dengan Docker — reproducible & scalable.",
    "Set 2FA everywhere — especially email & cloud accounts.",
    "Backup rutin: 3-2-1 rule (3 copies, 2 media, 1 offsite).",
    "Log rotation penting — disk penuh = server down.",
    "Use HTTPS always — Let's Encrypt untuk SSL gratis.",
    "Database connection pooling hindari 'too many connections'.",
    
    # System Design
    "Gunakan API versioning (/api/v1/) untuk backward compatibility.",
    "Rate your endpoints — latency < 200ms untuk API yang bagus.",
    "Don't trust user input — sanitize & validate semua data.",
    "Gunakan circuit breaker pattern untuk microservice resilience.",
    "Monitor dengan health checks — proactivity vs reactivity.",
    "Gunakan caching layer (Redis/Memcached) untuk read-heavy ops.",
    "Database read replica untuk scaling — primary hanya untuk writes.",
    
    # Security
    "Input validation is your first line of defense — validate di API layer.",
    "Use JWT dengan short expiry + refresh token mechanism.",
    "Never log sensitive data — mask passwords, tokens, PII.",
    "Set CORS policy yang ketat — jangan * di production.",
    "Use HTTPS everywhere — even internal service-to-service calls.",
    "Principle of least privilege — database user minimal permissions.",
    "Rate limit auth endpoints — brute force protection wajib.",
    
    # Performance
    "Lazy loading untuk gambar — gunakan loading='lazy' di img tag.",
    "Gunakan service worker untuk offline-capable web apps.",
    "Optimize images — next-gen format (WebP/AVIF) + proper sizing.",
    "Database query optimization: avoid N+1, use joins/select specific cols.",
    "Minify & gzip CSS/JS — bundle size reduction = faster TTFB.",
    "Use pagination untuk large dataset — jangan load all di memory.",
    "Gunakan Redis untuk session storage — faster than database.",
    
    # Tools
    "Git hooks untuk pre-commit: lint + test sebelum commit.",
    "Gunakan .gitignore yang tepat — jangan commit vendor/node_modules.",
    "CI/CD pipeline = build → test → deploy otomatis.",
    "Use meaningful commit messages — future you akan berterima kasih.",
    "Feature flags untuk gradual rollout — reduce blast radius.",
    "Gunakan monitoring (Prometheus/Grafana) sebelum incident terjadi.",
    "Structured logging (JSON) → easier parsing & alerting."
]

def get_todays_tip():
    """Get today's tech tip based on day of year."""
    from datetime import datetime
    day_of_year = datetime.now().timetuple().tm_yday
    return TIPS[day_of_year % len(TIPS)]

def search_tips(query):
    """Search tips by keyword."""
    results = []
    for tip in TIPS:
        if query.lower() in tip.lower():
            results.append(tip)
    return results

def get_all_categories():
    """Return category labels for tips."""
    categories = ["laravel", "php", "architecture", "devops", 
                  "security", "performance", "tools", "system-design"]
    return categories

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        query = sys.argv[1]
        tips = search_tips(query)
        print(f"Found {len(tips)} tips for '{query}':")
        for t in tips:
            print(f"  - {t}")
    else:
        print("Today's tip:")
        print(f"  {get_todays_tip()}")
        print(f"\nTotal tips in database: {len(TIPS)}")