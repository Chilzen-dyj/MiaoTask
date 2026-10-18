"""Compatibility entry point. Task logic lives in campaign.py."""
from modules.campaign import CampaignRunner, load_config


def run(device, config=None, auto_open=False, control=None, emit=None):
    """Run without interactive input; return verified task statistics."""
    return CampaignRunner(device, config or load_config(), control, emit).run(auto_open)
