"""Run with a disposable staff account: python tests/browser_admin_smoke.py URL USER PASSWORD."""
import sys
import time
from playwright.sync_api import sync_playwright, expect


def main(base_url, username, password):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base_url, wait_until='domcontentloaded')
        page.locator('#au-username').fill(username)
        page.locator('#au-password').fill(password)
        page.locator('#authSubmit').click()
        expect(page.locator('#appScreen')).to_be_visible()
        page.goto(base_url + '/workspace/#system', wait_until='domcontentloaded')
        expect(page.locator('#systemMetrics')).to_contain_text('İstifadəçi')
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        page.locator('#settingsForm [name=weighted_base_weight]').fill('3')
        page.locator('#settingsForm button').click()
        expect(page.locator('#message')).to_contain_text('Standart qaydalar yeniləndi')
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        assert page.evaluate("window.lunchClient.request('/settings/').then(data => data.weighted_base_weight)") == 3
        page.locator('#settingsForm [name=weighted_base_weight]').fill('1')
        page.locator('#settingsForm button').click()
        expect(page.locator('#settingsForm button')).to_be_enabled()
        expect(page.locator('#workspace')).to_have_attribute('aria-busy', 'false')
        page.goto(base_url + '/food-admin/', wait_until='domcontentloaded')
        expect(page.locator('#appScreen')).to_be_visible()
        name = 'Browser catalog ' + str(int(time.time()))
        page.locator('#nrName').fill(name)
        page.locator('#nrPrice').fill('20')
        page.locator('#nrAddress').fill('Smoke test address')
        page.locator('#nrWebsite').fill('https://example.org')
        page.locator('#nrRating').fill('4.4')
        page.locator('#saveRestaurant').click()
        expect(page.locator('#restaurantList')).to_contain_text(name)
        restaurant = page.locator('#restaurantList > div').filter(has_text=name)
        restaurant.get_by_role('button', name='Düzəliş').click()
        page.locator('#nrPrice').fill('22')
        page.locator('#saveRestaurant').click()
        expect(page.locator('#restaurantList')).to_contain_text('22.00')
        page.locator('#restaurantList > div').filter(has_text=name).click()
        page.locator('#miName').fill('Browser dish')
        page.locator('#miPrice').fill('7')
        page.locator('#miVeg').check()
        page.locator('#miVegan').check()
        page.locator('#miGlutenFree').check()
        page.locator('#saveMenuItem').click()
        expect(page.locator('#menuList')).to_contain_text('Browser dish')
        page.locator('#menuList').get_by_role('button', name='Düzəliş').click()
        page.locator('#miPrice').fill('8')
        page.locator('#saveMenuItem').click()
        expect(page.locator('#menuList')).to_contain_text('8.00')
        token = page.evaluate("localStorage.getItem('access')")
        headers = {'Authorization': 'Bearer ' + token}
        data = page.request.get(base_url + '/api/restaurants/?search=' + name, headers=headers).json()['results'][0]
        item = data['menu_items'][0]
        assert item['is_vegan'] and item['is_gluten_free'] and item['is_vegetarian']
        assert item['price'] == '8.00'
        assert page.request.delete(base_url + f"/api/restaurants/{data['id']}/", headers=headers).status == 204
        assert not errors, errors
        browser.close()
        print('Admin browser smoke passed: settings, system metrics, restaurant edits, menu edits and dietary flags.')


if __name__ == '__main__':
    main(*sys.argv[1:4])
