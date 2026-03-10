% File to analyse GVS data and compute COP
close all
clc

sample_rate = 960; % [Hz]
d = dir(cd); % Get directory listing
range = 0.07; % [m]

for i = 1:numel(d)
    fileName = d(i).name;
    if strcmp(fileName, 'MA_PILOT_JAN2625_01.mat')
        % Load force data
        forcesAndMoments = loadForcesFromHBCLBertecTreadmillMatFile(fileName, ...
            'forceFrequency', sample_rate, ...
            'shouldFilter', true, ...
            'filterCutoffFrequency', 30);
        
        % Extract data for left foot
        groundReactionMoments = forcesAndMoments.left.groundReactionMoments;
        groundReactionForces = forcesAndMoments.left.groundReactionForces;
        
        % Create time vector and remove first 3 seconds
        t = (0:length(groundReactionForces)-1)/sample_rate;
        idx_keep = t >= 3;  % Keep data from 3 seconds onward
        t = t(idx_keep);
        t = t - t(1);  % Reset time to start at 0
        
        groundReactionForces = groundReactionForces(idx_keep, :);
        groundReactionMoments = groundReactionMoments(idx_keep, :);
        
        % Calculate COP coordinates
        ry = groundReactionMoments(:,1) ./ groundReactionForces(:,3); % Mx/Fz
        rx = -groundReactionMoments(:,2) ./ groundReactionForces(:,3); % -My/Fz
        
        % Find peaks in COP y-coordinate
        figure;
        findpeaks(ry, 'MinPeakHeight', 0.44, 'MinPeakDistance', 3*sample_rate)
        [~, LOCS] = findpeaks(ry, 'MinPeakHeight', 0.44, 'MinPeakDistance', 3*sample_rate);
        title('Peaks in COP Y-Coordinate')
        xlabel('Time (s)')
        ylabel('COP Y Position (m)')
        
        % COP trajectory analysis around each peak
        xvar_idx = zeros(length(LOCS), 1);
        yvar_idx = zeros(length(LOCS), 1);
        
        for iPeak = 1:length(LOCS)
            figure;
            tmp_reach = 1 * sample_rate; % 1 second window around peak
            start_idx = max(1, LOCS(iPeak) - tmp_reach);
            end_idx = min(length(rx), LOCS(iPeak) + tmp_reach);
            idx_reach = start_idx:end_idx;
            
            % Plot COP trajectory
            plot(t(idx_reach), rx(idx_reach), 'b.'); 
            hold on;
            
            % Calculate and plot covariance ellipse
            C = cov([rx(idx_reach), ry(idx_reach)]);
            [eigvec, eigval] = eig(C);
            
            theta = linspace(0, 2*pi, 100);
            xy = [cos(theta'), sin(theta')] * sqrt(eigval) * eigvec';
            x_ellipse = xy(:,1) + mean(rx(idx_reach));
            y_ellipse = xy(:,2) + mean(ry(idx_reach));
            
            plot(x_ellipse, y_ellipse, 'r-', 'LineWidth', 2);
            
            title(sprintf('COP Trajectory Around Peak %d', iPeak))
            xlabel('COP X (m)')
            ylabel('COP Y (m)')
            axis equal
            grid on
            
            % Store variance
            xvar_idx(iPeak) = var(rx(idx_reach));
            yvar_idx(iPeak) = var(ry(idx_reach));
        end
        
        % Plot COP y-displacement over time
        figure;
        plot(t, ry, 'k');
        title('COP Y-Coordinate Displacement');
        xlabel('Time (s)');
        ylabel('COP Y (m)');
    end
end

% Plot variance results
if exist('xvar_idx', 'var') && exist('yvar_idx', 'var')
    figure;
    plot(xvar_idx, 'b-o', 'DisplayName', 'X Variance');
    hold on;
    plot(yvar_idx, 'r-s', 'DisplayName', 'Y Variance');
    title('Variance in COP During Reaching Tasks');
    xlabel('Peak Number');
    ylabel('Variance (m^2)');
    legend;
    grid on;
end