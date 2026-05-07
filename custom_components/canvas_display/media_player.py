"""Canvas Display — media_player platform.

Exposes each configured Canvas Display device as a HA media_player entity,
enabling TTS delivery and full audio playback via the standard HA media_player
service calls (play_media, volume_set, media_pause, etc.).

Audio is played on the device by mpv, controlled via the Canvas Display
REST API (POST /api/audio/*).  Volume is managed via pactl on the device.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CanvasDisplayCoordinator

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)

VOLUME_STEP = 0.10  # 10% per step


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Canvas Display media_player from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: CanvasDisplayCoordinator = entry_data["coordinator"]
    async_add_entities([CanvasDisplayMediaPlayer(coordinator, entry)])


class CanvasDisplayMediaPlayer(CoordinatorEntity[CanvasDisplayCoordinator], MediaPlayerEntity):
    """Represents a Canvas Display device as a HA media_player."""

    _attr_supported_features = SUPPORTED_FEATURES
    _attr_media_content_type = MediaType.MUSIC

    def __init__(
        self,
        coordinator: CanvasDisplayCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        settings = (coordinator.data or {}).get("settings", {})
        device_name = settings.get("device_name", "Canvas Display")
        self._attr_name = f"{device_name} Audio"
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": device_name,
            "manufacturer": "Canvas Display",
        }
        # Last known volume before mute (for unmute restore)
        self._premute_volume: float | None = None

    # ── State helpers ──────────────────────────────────────────────────────────

    @property
    def _audio(self) -> dict:
        """Return the audio sub-dict from coordinator data."""
        return (self.coordinator.data or {}).get("audio_state", {})

    @property
    def state(self) -> MediaPlayerState:
        if not (self.coordinator.data or {}).get("online", False):
            return MediaPlayerState.OFF
        play_state = self._audio.get("state", "idle")
        return {
            "playing": MediaPlayerState.PLAYING,
            "paused":  MediaPlayerState.PAUSED,
            "idle":    MediaPlayerState.IDLE,
        }.get(play_state, MediaPlayerState.IDLE)

    @property
    def volume_level(self) -> float | None:
        vol = self._audio.get("volume")
        return vol / 100.0 if vol is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        return self._audio.get("muted", False)

    @property
    def media_title(self) -> str | None:
        return self._audio.get("title") or None

    @property
    def media_content_id(self) -> str | None:
        return self._audio.get("url") or None

    # ── Commands ───────────────────────────────────────────────────────────────

    async def async_turn_on(self) -> None:
        """Turn on — restore unmuted audio and wake screen."""
        try:
            await self.coordinator.async_screen_on()
        except Exception as err:
            _LOGGER.warning("turn_on (screen_on) failed: %s", err)

    async def async_turn_off(self) -> None:
        """Turn off — stop audio and put screen to sleep."""
        try:
            await self.coordinator.async_audio_stop()
        except Exception as err:
            _LOGGER.warning("turn_off (audio_stop) failed: %s", err)
        try:
            await self.coordinator.async_screen_off()
        except Exception as err:
            _LOGGER.warning("turn_off (screen_off) failed: %s", err)
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        await self.coordinator.async_audio_resume()
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        await self.coordinator.async_audio_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        await self.coordinator.async_audio_stop()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        level = round(volume * 100)
        await self.coordinator.async_audio_volume(level)
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        current = self.volume_level or 0.0
        await self.async_set_volume_level(min(1.0, current + VOLUME_STEP))

    async def async_volume_down(self) -> None:
        current = self.volume_level or 0.0
        await self.async_set_volume_level(max(0.0, current - VOLUME_STEP))

    async def async_mute_volume(self, mute: bool) -> None:
        if mute and not self.is_volume_muted:
            self._premute_volume = self.volume_level
        await self.coordinator.async_audio_mute(mute)
        await self.coordinator.async_request_refresh()

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play audio from a URL.

        Works with HA TTS:
          service: tts.speak
          data:
            media_player_entity_id: media_player.canvas_display_audio
            message: "Hello from Home Assistant"
        """
        title: str | None = kwargs.get("extra", {}).get("title")
        volume: int | None = None
        if (current := self.volume_level) is not None:
            volume = round(current * 100)
        await self.coordinator.async_audio_play(media_id, title=title, volume=volume)
        await self.coordinator.async_request_refresh()
