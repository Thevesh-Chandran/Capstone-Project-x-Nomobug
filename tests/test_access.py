import pytest

from webapp import access


@pytest.fixture
def fake_iap(monkeypatch):
    state = {'policy': {'etag': 'e1', 'bindings': [
        {'role': access.ROLE, 'members': ['user:thevesh20@gmail.com', 'user:staff@gmail.com']},
        {'role': 'roles/iap.admin', 'members': ['serviceAccount:portal@example.iam.gserviceaccount.com']},
    ]}, 'set': []}

    def call(method, body):
        if method == 'getIamPolicy':
            return state['policy']
        state['set'].append(body['policy'])
        state['policy'] = body['policy']
        return body['policy']

    monkeypatch.setattr(access, '_call', call)
    monkeypatch.setenv('CP2_ACCESS_ADMINS', 'thevesh20@gmail.com')
    return state


def test_only_owner_is_admin(monkeypatch):
    monkeypatch.setenv('CP2_ACCESS_ADMINS', 'thevesh20@gmail.com')
    assert access.is_admin('Thevesh20@gmail.com')
    assert not access.is_admin('staff@gmail.com')
    assert not access.is_admin(None)


def test_members_lists_only_the_sign_in_role(fake_iap):
    assert access.members() == ['staff@gmail.com', 'thevesh20@gmail.com']


def test_add_and_remove_change_only_the_sign_in_role(fake_iap):
    assert 'new@gmail.com' in access.change('add', 'New@gmail.com', 'thevesh20@gmail.com')
    assert 'staff@gmail.com' not in access.change('remove', 'staff@gmail.com', 'thevesh20@gmail.com')
    roles = {b['role']: b['members'] for b in fake_iap['policy']['bindings']}
    assert roles['roles/iap.admin'] == ['serviceAccount:portal@example.iam.gserviceaccount.com']
    assert fake_iap['set'][-1]['etag'] == 'e1'  # the etag is sent back, so a concurrent change is refused


def test_owner_cannot_be_removed_and_bad_emails_are_refused(fake_iap):
    with pytest.raises(ValueError):
        access.change('remove', 'thevesh20@gmail.com', 'thevesh20@gmail.com')
    with pytest.raises(ValueError):
        access.change('add', 'not-an-email', 'thevesh20@gmail.com')
    with pytest.raises(ValueError):
        access.change('drop', 'x@gmail.com', 'thevesh20@gmail.com')
    assert fake_iap['set'] == []
