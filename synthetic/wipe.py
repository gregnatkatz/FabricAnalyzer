"""Phase 6 — Wipe: deletes synthetic data for a session.
Always verifies deletion with os.path.exists() check.
"""
import os
import shutil
import sys


def wipe_session(session_id, tmp_dir='./tmp'):
    """Wipe all synthetic data for a session.
    
    Returns:
        dict with status and verification result
    """
    session_dir = os.path.join(tmp_dir, session_id)

    if not os.path.exists(session_dir):
        return {
            'status': 'ok',
            'message': f'Session dir does not exist: {session_dir}',
            'verified': True,
        }

    try:
        shutil.rmtree(session_dir)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to delete: {e}',
            'verified': False,
        }

    # Verify deletion — REQUIRED by spec
    still_exists = os.path.exists(session_dir)
    if still_exists:
        return {
            'status': 'error',
            'message': f'Wipe verification FAILED — {session_dir} still exists',
            'verified': False,
        }

    return {
        'status': 'ok',
        'message': f'Wiped session: {session_id}',
        'verified': True,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python wipe.py <session_id> [tmp_dir]')
        sys.exit(1)
    session = sys.argv[1]
    tmp = sys.argv[2] if len(sys.argv) > 2 else './tmp'
    result = wipe_session(session, tmp)
    print(result)
    if not result['verified']:
        sys.exit(1)
