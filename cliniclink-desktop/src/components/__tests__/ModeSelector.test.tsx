import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ModeSelector from '../ModeSelector';
import * as sidecar from '../../api/sidecar';

vi.mock('../../api/sidecar', () => ({
  setMode: vi.fn().mockResolvedValue(undefined),
}));

const mockedSetMode = vi.mocked(sidecar.setMode);

describe('ModeSelector', () => {
  beforeEach(() => {
    mockedSetMode.mockClear();
  });

  test('renders mode buttons', () => {
    render(<ModeSelector />);
    expect(screen.getByText('Clinic')).toBeInTheDocument();
    expect(screen.getByText('Ambulance')).toBeInTheDocument();
  });

  test('selecting Clinic calls sidecar setMode and updates UI state', async () => {
    render(<ModeSelector />);
    fireEvent.click(screen.getByText('Clinic'));

    await waitFor(() => {
      expect(mockedSetMode).toHaveBeenCalledWith('clinic');
    });
  });

  test('selecting Ambulance calls sidecar setMode', async () => {
    render(<ModeSelector />);
    fireEvent.click(screen.getByText('Ambulance'));

    await waitFor(() => {
      expect(mockedSetMode).toHaveBeenCalledWith('ambulance');
    });
  });

  test('displays an error when setMode fails', async () => {
    mockedSetMode.mockRejectedValueOnce(new Error('sidecar unavailable'));
    render(<ModeSelector />);
    fireEvent.click(screen.getByText('Clinic'));

    expect(await screen.findByRole('alert')).toHaveTextContent('sidecar unavailable');
  });
});
