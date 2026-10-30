"""Run against a disposable, seeded app: python tests/browser_smoke.py [base_url].

Requires `pip install playwright` and `python -m playwright install chromium`.
Uses demo accounts; creates and removes its own team and session.
"""
import sys
import time
import urllib.request
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright, expect


def main(base_url):
    deadline = time.monotonic() + 30
    while True:
        try:
            urllib.request.urlopen(base_url + '/health/', timeout=1).close()
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept())
        page.goto(base_url, wait_until='domcontentloaded')
        page.locator('#au-username').fill('sabina')
        page.locator('#au-password').fill('lunch1234')
        page.locator('#authSubmit').click()
        expect(page.locator('#appScreen')).to_be_visible()
        page.goto(base_url + '/workspace/', wait_until='domcontentloaded')
        expect(page.locator('#workspace')).to_be_visible()
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        name = 'Browser smoke ' + str(int(time.time()))
        page.locator('#createTeamForm [name=name]').fill(name)
        page.locator('#createTeamForm [name=description]').fill('Disposable browser verification')
        page.locator('#createTeamForm button').click()
        expect(page.locator('#teamHeading')).to_have_text(name)
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        team_id = page.locator('#teamSelect').input_value()
        page.locator('#inviteMemberForm [name=username]').fill('ali')
        page.locator('#inviteMemberForm [name=role]').select_option('guest')
        page.locator('#inviteMemberForm button').click()
        expect(page.locator('#members')).to_contain_text('ali')
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        page.locator('#members select').select_option('member')
        page.get_by_role('button', name='Rol dəyiş', exact=True).click()
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        expect(page.locator('#members select')).to_have_value('member')
        page.locator('#inviteLinkForm button').click()
        expect(page.locator('#newInviteWrap')).to_be_visible()
        invite_url = page.locator('#newInvite').input_value()
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')

        guest_context = browser.new_context()
        guest = guest_context.new_page()
        guest.on('pageerror', lambda error: errors.append(str(error)))
        guest.goto(invite_url, wait_until='domcontentloaded')
        expect(guest.locator('#teamName')).to_have_text(name)
        guest.locator('#joinBtn').click()
        guest.locator('#au-username').fill('reshad')
        guest.locator('#au-password').fill('lunch1234')
        guest.locator('#authSubmit').click()
        expect(guest.locator('#teamName')).to_have_text(name)
        guest.locator('#joinBtn').click()
        expect(guest.locator('#appScreen')).to_be_visible(timeout=15000)
        expect(guest.locator('#mainTeamSelect')).to_have_value(team_id)

        page.get_by_role('button', name='Sessiyalar', exact=True).click()
        now = datetime.now()
        page.locator('#sessionForm [name=title]').fill('Browser rating lunch')
        page.locator('#sessionForm [name=start_time]').fill((now - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M'))
        page.locator('#sessionForm [name=end_time]').fill((now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
        page.locator('#sessionForm [name=voting_mode]').select_option('rating')
        page.locator('#sessionForm [name=recurrence_rule]').select_option('weekly')
        page.locator('#saveSession').click()
        expect(page.locator('#sessions')).to_contain_text('Browser rating lunch')
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        token = page.evaluate("localStorage.getItem('access')")
        headers = {'Authorization': 'Bearer ' + token}
        response = context.request.get(base_url + '/api/sessions/?team=' + team_id, headers=headers)
        session = response.json()['results'][0]
        restaurants = context.request.get(base_url + '/api/restaurants/', headers=headers).json()['results']
        response = context.request.post(base_url + f"/api/sessions/{session['id']}/proposals/", headers=headers, data={'restaurant': restaurants[0]['id']})
        assert response.status == 201, response.text()
        page.goto(base_url + f"/?team={team_id}&session={session['id']}", wait_until='domcontentloaded')
        expect(page.locator('.proposal-card')).to_have_count(1)
        page.locator('.rating-select').select_option('2')
        page.locator('.vote-btn').click()
        expect(page.locator('.vote-btn')).to_contain_text('2')
        page.locator('.rating-select').select_option('4')
        expect(page.locator('.vote-btn')).to_contain_text('4')
        votes = context.request.get(base_url + f"/api/sessions/{session['id']}/votes/", headers=headers).json()
        assert len(votes) == 1 and votes[0]['choice'] == 4
        page.locator('.vote-btn').click()
        expect(page.locator('.vote-count')).to_have_text('0')
        page.goto(base_url + '/workspace/#history', wait_until='domcontentloaded')
        expect(page.locator('[data-panel=history]')).to_be_visible()
        page.get_by_role('button', name='Profil', exact=True).click()
        expect(page.locator('#profileForm [name=username]')).to_have_value('sabina')
        page.get_by_role('button', name='Komandalar', exact=True).click()
        page.screenshot(path='.verify/workspace.png', full_page=True)
        page.locator('#deleteTeam').click()
        expect(page.locator('#teamHeading')).not_to_have_text(name)
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        assert not errors, errors
        guest_context.close()
        browser.close()
        print('Browser smoke passed: team creation, roles, invite/login/join, recurring session, rating updates/removal, history, profile, and cleanup.')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000')
