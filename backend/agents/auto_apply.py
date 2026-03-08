"""
Auto-Apply Agent — attempts to auto-apply to LinkedIn Easy Apply jobs.
Returns (success: bool, note: str).
"""
import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

RESUME_PDF_PATH = str(Path(__file__).parent.parent / "resume" / "Pavan_Ram_Resume_1.pdf")


async def try_apply_linkedin(job_url: str, linkedin_email: str, linkedin_password: str) -> tuple[bool, str]:
    """
    Attempt LinkedIn Easy Apply using Playwright.
    Returns (success, note).
    """
    if not job_url or "linkedin.com" not in job_url:
        return False, "Not a LinkedIn job URL — apply manually"

    if not linkedin_email or not linkedin_password:
        return False, "LinkedIn credentials not configured in .env — apply manually"

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return False, "Playwright not installed — apply manually"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Login
            await page.goto("https://www.linkedin.com/login", timeout=20000)
            await page.fill("#username", linkedin_email)
            await page.fill("#password", linkedin_password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle", timeout=15000)

            if "checkpoint" in page.url or "login" in page.url:
                await browser.close()
                return False, "LinkedIn login failed or requires 2FA — apply manually"

            # Navigate to job
            await page.goto(job_url, timeout=20000)
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Check for Easy Apply button
            easy_apply_btn = await page.query_selector("button.jobs-apply-button:has-text('Easy Apply')")
            if not easy_apply_btn:
                await browser.close()
                return False, "No Easy Apply button — apply manually via link"

            await easy_apply_btn.click()
            await asyncio.sleep(2)

            # Check if multi-step or single-step
            # Try to proceed through form pages (basic handling)
            for step in range(5):
                next_btn = await page.query_selector("button:has-text('Next')")
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(1.5)
                    continue

                submit_btn = await page.query_selector("button:has-text('Submit application')")
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(2)
                    await browser.close()
                    return True, "Applied via LinkedIn Easy Apply"

                # If there are required fields we can't fill, stop
                review_btn = await page.query_selector("button:has-text('Review')")
                if review_btn:
                    await review_btn.click()
                    await asyncio.sleep(1.5)
                    continue

                break

            await browser.close()
            return False, "Easy Apply form has complex fields (work auth, screening questions) — apply manually"

        except Exception as e:
            await browser.close()
            logger.warning(f"Playwright apply error: {e}")
            return False, f"Auto-apply failed ({str(e)[:80]}) — apply manually"


def try_apply(source: str, job_url: str) -> tuple[bool, str]:
    """
    Synchronous wrapper. Decides which apply strategy to use.
    """
    linkedin_email = os.getenv("LINKEDIN_EMAIL", "")
    linkedin_password = os.getenv("LINKEDIN_PASSWORD", "")

    if source == "linkedin":
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                try_apply_linkedin(job_url, linkedin_email, linkedin_password)
            )
            loop.close()
            return result
        except Exception as e:
            return False, f"LinkedIn apply error: {e} — apply manually"

    elif source == "naukri":
        return False, "Naukri auto-apply requires account login via app — apply manually"

    elif source == "indeed":
        return False, "Indeed auto-apply requires account login — apply manually"

    else:
        return False, "Unknown source — apply manually via the job link"
