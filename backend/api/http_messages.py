"""User-facing text for common HTTP error responses (API-wide)."""

HTTP_403 = "You don't have permission to access this resource."
HTTP_404 = "The requested resource was not found."
HTTP_429 = "Too many requests. Please slow down and try again later."
HTTP_500 = "An internal error occurred. Please try again later."
HTTP_503 = "The service is temporarily unavailable. Please try again later."
# For validation / bad input not covered by the list above (e.g. database constraints)
HTTP_400 = "The request could not be completed. Please check your information and try again."
