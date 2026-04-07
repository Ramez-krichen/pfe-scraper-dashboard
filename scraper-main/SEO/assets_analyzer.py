def analyze_assets(page):
    asset_responses = {}

    # Listen to all network responses
    def on_response(response):
        url = response.url
        resource_type = _get_resource_type(url, response)

        # Store response details for matching URLs
        asset_responses[url] = {
            'url': url,
            'status_code': response.status,
            'headers': response.headers,
            'resource_type': resource_type,
            'timing': response.request.timing
        }

    page.on('response', on_response)