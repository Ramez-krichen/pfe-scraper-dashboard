import httpx
import logging

logger = logging.getLogger(__name__)

class WebhookNotifier:
    def __init__(self, timeout_seconds=10.0):
        self.timeout = timeout_seconds

    def send_payload(self, job):
        """
        Sends the job payload to the webhook_url specified in the job metadata.
        Returns True if successful or no webhook_url was provided, False otherwise.
        """
        metadata = job.get("metadata", {})
        webhook_url = metadata.get("webhook_url")

        if not webhook_url:
            return True

        logger.info(f"Sending webhook for job {job['id']} to {webhook_url}")

        try:
            # Send the entire job object as JSON payload, or customize as needed
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(webhook_url, json=job)

            if response.status_code >= 400:
                logger.warning(
                    f"Webhook for job {job['id']} returned HTTP {response.status_code}: {response.text}"
                )
                return False

            logger.info(f"Successfully sent webhook for job {job['id']}")
            return True

        except httpx.RequestError as e:
            logger.error(f"Failed to send webhook for job {job['id']} to {webhook_url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending webhook for job {job['id']}: {e}")
            return False
