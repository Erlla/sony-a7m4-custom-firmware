"""p1 completion is separate from Windows storage-driver restoration."""


def complete(record):
    if not isinstance(record, dict):
        return False
    if record.get('read_verified') is not True or record.get('session_ended') is not True:
        return False
    if record.get('phase') == 'COMPLETE':
        return record.get('normal_recovery_verified') is True
    return (record.get('phase') == 'P1_COMPLETE'
            and record.get('driver_policy') == 'retain'
            and record.get('p1_operation_complete') is True)
