import { renderHook, act, waitFor } from '@testing-library/react';
import { useSidecarEvent } from '../useEvents';
import { listen } from '@tauri-apps/api/event';

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(),
}));

const mockedListen = vi.mocked(listen);

describe('useSidecarEvent', () => {
  let capturedHandler: ((event: { payload: string }) => void) | undefined;
  let unlistenFn: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    capturedHandler = undefined;
    unlistenFn = vi.fn();
    mockedListen.mockImplementation(async (eventName, handler) => {
      if (eventName === 'cliniclink:event') {
        capturedHandler = handler as (event: { payload: string }) => void;
      }
      return unlistenFn;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  test('subscribes to cliniclink:event channel', () => {
    renderHook(() => useSidecarEvent(vi.fn()));
    expect(mockedListen).toHaveBeenCalledWith('cliniclink:event', expect.any(Function));
  });

  test('parses and forwards events to the callback', () => {
    const callback = vi.fn();
    renderHook(() => useSidecarEvent(callback));

    const event = {
      type: 'heartbeat',
      timestamp: '2026-07-17T06:57:46.000Z',
      payload: { status: 'ok' },
    };

    act(() => {
      capturedHandler?.({ payload: JSON.stringify(event) });
    });

    expect(callback).toHaveBeenCalledWith(event);
  });

  test('ignores malformed JSON payloads', () => {
    const callback = vi.fn();
    renderHook(() => useSidecarEvent(callback));

    act(() => {
      capturedHandler?.({ payload: 'not-json' });
    });

    expect(callback).not.toHaveBeenCalled();
  });

  test('unsubscribes on unmount', async () => {
    const { unmount } = renderHook(() => useSidecarEvent(vi.fn()));
    unmount();
    await waitFor(() => expect(unlistenFn).toHaveBeenCalledTimes(1));
  });
});
