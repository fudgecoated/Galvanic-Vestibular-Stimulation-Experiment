% file to analyse gvs data and compute cop
%clear
close all
clc
sample_rate=960; % [Hz]
d=dir('C:\Users\munib\Documents\PandasForGVS\APR242023 Pilot'); % file listing of current directory (cd)
names=d.name; % names of files
n=size(d);
range=0.07; % [m]

for i=1:max(n)%i=max(n)-2 %
    fileName=d(i).name;
    fileType=finfo(fileName);
    %if strcmp(fileType,'mat')
    if strcmp(fileName,'akbarpilot_05_01.mat')
        [forcesAndMoments] = loadForcesFromHBCLBertecTreadmillMatFile(fileName,'forceFrequency',[sample_rate],'shouldFilter',[1],'filterCutoffFrequency',[30]);
        groundReactionMoments=forcesAndMoments.left.groundReactionMoments; % [Nm], measured at 1000 Hz, maybe ??
        groundReactionForces=forcesAndMoments.left.groundReactionForces; % [N], measured at 1000 Hz, maybe ??
        t=(0:length(groundReactionForces)-1)/sample_rate;
        idx_cut= t<3; % indexing every sample after t=5
        t(idx_cut)=[];
        t=t-t(1); % to make sure time axis starts at 0
        groundReactionForces(idx_cut,:)=[]; % trow away everything after 5 seconds
        groundReactionMoments(idx_cut,:)=[]; % trow away everything after 5 seconds
        % cop position wrt back left side of treadmill. positive x-direction in the
        % walking direction. positive y-direction towards middle
        ry=groundReactionMoments(:,1)./groundReactionForces(:,3); % [m]
        rx=-groundReactionMoments(:,2)./groundReactionForces(:,3); % [m]
        
        
        % find peaks in v_cop
        figure;
        [~,LOCS] = findpeaks(ry,'MinPeakDistance',3*sample_rate,'MinPeakHeight',0.44);
        findpeaks(ry,sample_rate,'MinPeakDistance',3,'MinPeakHeight',0.44)
        %ylim ([0 0.7])
        xticks([0 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80 85 90 95 100])
        xlabel('Time [s]')
        ylabel('COP velocity [m/s]')
        axis equal
        
        for iPeak2=1:length(LOCS)
%             figure;
%             xlabel('time')
%             ylabel('COPx')
            tmp_reach=1*sample_rate; % nr of samples to look at to the left and right of a peak
            idx_reach=LOCS(iPeak2)-tmp_reach:LOCS(iPeak2)+tmp_reach; %for every location detected, take all samples +/- x seconds from the peak
            %plot(t(idx_reach),rx(idx_reach),'.'); hold on
            
            %create a column for the variance per reach in a given
            %condition
            xvar_idx(iPeak2,1) = var(rx(idx_reach));
            yvar_idx(iPeak2,1) = var(ry(idx_reach));
            
%             n=100; % Number of points around ellipse
%             p=0:pi/n:2*pi; % angles around a circle
%             C = cov([rx(idx_reach) ry(idx_reach)]); % covariance of rx and ry
%             [eigvec,eigval] = eig(C) % Compute eigen-stuff
%             xy_r = [cos(p'),sin(p')] * sqrt(eigval) * eigvec'; % Transformation
%             x_ellips_reach = xy_r(:,1) + mean(rx(idx_reach));
%             y_ellips_reach = xy_r(:,2) + mean(ry(idx_reach));
%             plot(x_ellips_reach,y_ellips_reach,'ro')
        end
       
        xvar = var(rx)
        yvar = var(ry)
        
        figure;
        plot(t,ry, 'k')
        title('y-Coordinate Displacement in COP during the Reaching Task', 'FontSize', 24)
        xlabel('Time (s)')
        ylabel('COPy (m)')
        
    end
end

figure
plot(xvar_idx); hold on
plot(yvar_idx); hold on


figure
plot(c1_xvar_tn, 'ko-', 'LineWidth', 0.2); hold on
plot(c2_xvar_tn, 'k^-.', 'LineWidth', 0.2); hold on
plot(c3_xvar_tn, 'k^-', 'LineWidth', 0.2); hold on
plot(c4_xvar_tn, 'k*-.', 'LineWidth', 0.2); hold on
plot(c5_xvar_tn, 'k*-', 'LineWidth', 0.2); hold on
title('Variance in the Left-Right Direction COP during Various Reaching Conditions', 'FontSize', 22)
xlabel('Trial Number (#)', 'FontSize', 18)
ylabel('Total Variance', 'FontSize', 18)
legend('No vision, no GVS','Vision, no weight','No vision, no weight','Vision, weight','No vision, weight'); hold on
