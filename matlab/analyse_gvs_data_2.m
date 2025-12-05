% File to analyze GVS data and compute COP
close all;
clc;

sample_rate = 960; % [Hz]
d = dir(cd); % File listing of current directory
range = 0.07; % [m]

for i = 1:numel(d)
    fileName = d(i).name;
    if strcmp(fileName, 'MA_PILOT_JAN2625_01.mat')
        % Load force data
        forcesAndMoments = loadForcesFromHBCLBertecTreadmillMatFile(fileName, ...
            'forceFrequency', sample_rate, 'shouldFilter', 1, 'filterCutoffFrequency', 30);
        
        % Extract forces and moments
        groundReactionMoments = forcesAndMoments.left.groundReactionMoments;
        groundReactionForces = forcesAndMoments.left.groundReactionForces;
        
        % Create time vector and trim initial 3 seconds
        t = (0:length(groundReactionForces)-1)/sample_rate;
        idx_keep = t >= 3; % Keep data from 3 seconds onward
        t = t(idx_keep);
        t = t - t(1); % Reset time to start at 0
        groundReactionForces = groundReactionForces(idx_keep, :);
        groundReactionMoments = groundReactionMoments(idx_keep, :);
        
        % Calculate COP coordinates
        ry = groundReactionMoments(:, 1) ./ groundReactionForces(:, 3); % [m]
        rx = -groundReactionMoments(:, 2) ./ groundReactionForces(:, 3); % [m]
        
        % Find peaks in COP y-coordinate
        figure;
        findpeaks(ry, sample_rate, 'MinPeakDistance', 3, 'MinPeakHeight', 0.44);
        title('Peaks in COP Y-Coordinate');
        xlabel('Time [s]');
        ylabel('COPy [m]');
        
        [~, LOCS] = findpeaks(ry, 'MinPeakDistance', 3*sample_rate, 'MinPeakHeight', 0.44);
        
        % Analyze COP trajectories around each peak
        xvar_idx = zeros(length(LOCS), 1);
        yvar_idx = zeros(length(LOCS), 1);
        
        for iPeak = 1:length(LOCS)
            figure;
            tmp_reach = 1 * sample_rate; % 1 second window around peak
            idx_reach = max(1, LOCS(iPeak)-tmp_reach) : min(length(rx), LOCS(iPeak)+tmp_reach);
            
            % Plot COP trajectory
            plot(rx(idx_reach), ry(idx_reach), '.'); 
            hold on;
            
            % Calculate and plot covariance ellipse
            C = cov([rx(idx_reach), ry(idx_reach)]);
            [eigvec, eigval] = eig(C);
            n = 100; % Points on ellipse
            theta = linspace(0, 2*pi, n);
            xy = [cos(theta'), sin(theta')] * sqrt(eigval) * eigvec';
            x_ellipse = xy(:,1) + mean(rx(idx_reach));
            y_ellipse = xy(:,2) + mean(ry(idx_reach));
            plot(x_ellipse, y_ellipse, 'r-', 'LineWidth', 1.5);
            
            title(sprintf('COP Trajectory Around Peak %d', iPeak));
            xlabel('COPx [m]');
            ylabel('COPy [m]');
            axis equal;
            
            % Store variances
            xvar_idx(iPeak) = var(rx(idx_reach));
            yvar_idx(iPeak) = var(ry(idx_reach));
        end
        
        % Plot time series of COP y-coordinate
        figure;
        plot(t, ry, 'k');
        title('COP Y-Coordinate Time Series');
        xlabel('Time (s)');
        ylabel('COPy (m)');
    end
end

% Plot variance metrics
figure;
plot(xvar_idx, 'bo-', 'DisplayName', 'X Variance');
hold on;
plot(yvar_idx, 'ro-', 'DisplayName', 'Y Variance');
title('Variance in COP During Reaching Tasks');
xlabel('Peak Number');
ylabel('Variance [m^2]');
legend('show');
grid on;