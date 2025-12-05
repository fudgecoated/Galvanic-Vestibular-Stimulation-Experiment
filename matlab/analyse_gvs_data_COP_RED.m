% Ensure sample_rate is defined (adjust value if needed)
close all;
clc;

sample_rate = 960; % Typically 960 Hz based on comments

% Loop through files (assuming 'd' is a directory listing)
for i = 1:length(d) % Fixed from max(n) to length(d)
    fileName = d(i).name;
    if strcmp(fileName, 'MA_PILOT_JAN2625_01.mat')
        % Load force data
        [forcesAndMoments] = loadForcesFromHBCLBertecTreadmillMatFile(fileName,...
            'forceFrequency', sample_rate,...
            'shouldFilter', 1,...
            'filterCutoffFrequency', 30);
        
        % Extract data
        groundReactionMoments = forcesAndMoments.left.groundReactionMoments;
        groundReactionForces = forcesAndMoments.left.groundReactionForces;
        t = (0:length(groundReactionForces)-1)/sample_rate;
        
        % Trim data to 30-90 seconds
        idx_cut = t > 110 | t < 5;
        t(idx_cut) = [];
        groundReactionForces(idx_cut,:) = [];
        groundReactionMoments(idx_cut,:) = [];
        t = t - t(1); % Reset to start at 0
        
        % Calculate COP coordinates
        ry = groundReactionMoments(:,1)./groundReactionForces(:,3);
        rx = -groundReactionMoments(:,2)./groundReactionForces(:,3);
        
        % Calculate COP velocity
        ryd = diff(ry)*sample_rate;
        rxd = diff(rx)*sample_rate;
        v_r = sqrt(ryd.^2 + rxd.^2);
        
        % Find peaks in velocity magnitude
        [~, LOCS] = findpeaks(v_r,...
            'MinPeakHeight', 0.1,...
            'MinPeakDistance', 2*sample_rate); % Adjusted for better peak detection
        
        % Adjust for diff offset
        LOCS = LOCS + 1;
        LOCS(LOCS > length(t)) = length(t); % Ensure valid indices
                
        for iPeak=1:length(LOCS) % we are gonna do something for every peak
        figure
        axis equal; hold on %this will ensure axis are in similar proportions. NEED TO ALTER THE LIMITS BASED ON TRIAL
        xlabel('Left-Right Sway (m)', 'FontSize', 20)
        ylabel('Front-Back sway (m)', 'FontSize', 20)
        title('x- and y-Coordinate COP Profile During Constant Current GVS', 'FontSize', 24)
        time_span=10*sample_rate; % nr of samples to look at round peak
        time_gvs=3*sample_rate;
        idx_tmp=LOCS(iPeak)-time_span:LOCS(iPeak)+time_span;
        idx_gvs=LOCS(iPeak)-time_gvs:LOCS(iPeak)+time_gvs;
        plot(rx(idx_tmp),ry(idx_tmp),'k.'); hold on
        plot(rx(idx_gvs),ry(idx_gvs),'r-','linewidth',2); hold on
        %legend('Constant Current','GVS ON/OFF Switch');
%         % Create 2D COP trajectory plots with peak highlighting
%         for iPeak = 1:length(LOCS)
%             peak_time = t(LOCS(iPeak));
%             
%             % Create 10-second window (5 seconds before/after)
%             time_window = 5; % ±5 seconds
%             window_mask = (t >= peak_time - time_window) & (t <= peak_time + time_window);
%             
%             % Create 3-second highlight (1.5 seconds before/after)
%             highlight_window = 1.5; % ±1.5 seconds
%             highlight_mask = (t >= peak_time - highlight_window) & (t <= peak_time + highlight_window);
%             
%             % Create plot
%             figure;
%             
%             % Plot full window in black
%             plot(rx(window_mask), ry(window_mask), 'k-',...
%                 'DisplayName', 'Full Trajectory',...
%                 'LineWidth', 0.5);
%             hold on;
%             
%             % Plot highlighted section in red
%             plot(rx(highlight_mask & window_mask), ry(highlight_mask & window_mask),...
%                 'r-', 'LineWidth', 2, 'DisplayName', 'GVS Period');
%             
%             % Add marker at peak location
%             plot(rx(LOCS(iPeak)), ry(LOCS(iPeak)), 'bo',...
%                 'MarkerFaceColor', 'b',...
%                 'DisplayName', 'Peak Location');
%             
%             % Formatting
%             title(sprintf('COP Trajectory Around Peak at %.1f seconds', peak_time));
%             xlabel('COPx (m)');
%             ylabel('COPy (m)');
%             legend('Location', 'best');
%             axis equal;
%             grid on;
%             
            % Set consistent axis limits if needed
            % xlim([-0.40 -0.20]);
            % ylim([0.35 0.55]);
        end
        
    end
end