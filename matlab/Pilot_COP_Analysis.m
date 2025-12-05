clear
close all
clc

directoryPath = 'C:\Users\munib\Documents\PandasForGVS';
cd(directoryPath);
sample_rate=960; % [Hz of Treadmill]
load("TA_COPILOT_05_01_01.mat", 'realtime', 'samples', 'samplesHandrail', 'time'); %load original raw force plate data
filename = 'treadmillRawData.mat';
save(filename,'realtime', 'samples', 'samplesHandrail', 'time');

[forcesAndMoments] = loadForcesFromHBCLBertecTreadmillMatFile('treadmillRawData.mat','forceFrequency',[sample_rate],'shouldFilter',[1],'filterCutoffFrequency',[30]);
groundReactionMoments=forcesAndMoments.left.groundReactionMoments; % [Nm], measured at 1000 Hz, maybe ??
groundReactionForces=forcesAndMoments.left.groundReactionForces; % [N], measured at 1000 Hz, maybe ??
t=(0:length(groundReactionForces)-1)/sample_rate;
idx_cut=t>400 | t<5; % indexing every sample after t=500 and before t=60
t(idx_cut)=[];
t=t-t(1); % to make sure time axis starts at 0
groundReactionForces(idx_cut,:)=[]; % trow away everything after 525 seconds
groundReactionMoments(idx_cut,:)=[]; % trow away everything after 525 seconds
% cop position wrt back left side of treadmill. positive x-direction in the
% walking direction. positive y-direction towards middle
ry=groundReactionMoments(:,1)./groundReactionForces(:,3); % [m]
rx=-groundReactionMoments(:,2)./groundReactionForces(:,3); % [m]

ryd=diff(ry)*sample_rate; % [m/s] velocity of cop in y direction. delta y / delta time (1/sf)
rxd=diff(rx)*sample_rate;
v_r=sqrt(ryd.^2+rxd.^2); %computes the magnitude of the velocity coordinates (pythagoras)

figure;plot(rx,ry)
xticks("auto")
title('y coordinate over time')
xlabel('COPx (m)')
ylabel('COPy (m)')

%find peaks in v_cop
figure;
[~,LOCS] = findpeaks(rxd,'MinPeakDistance',30*sample_rate,'MinPeakHeight',0.05, 'NPeaks',6);
findpeaks(rxd,sample_rate,'MinPeakDistance',30,'MinPeakHeight',0.05,'NPeaks',6)
xticks([0 30 60 90])
xlabel('Time (s)')
ylabel('COP velocity (m/s)')

for iPeak=1:length(LOCS) % we are gonna do something for every peak
    figure
    axis equal; hold on %this will ensure axis are in similar proportions. NEED TO ALTER THE LIMITS BASED ON TRIAL
    xlabel('Left-Right Sway (m)')
    ylabel('Front-Back sway (m)')
    title('x- and y-Coordinate COP Profile During Constant Current GVS')
    time_span=7*sample_rate; % nr of samples to look at round peak
    time_gvs=5*sample_rate;
    idx_tmp=LOCS(iPeak)-time_span:LOCS(iPeak)+time_span;
    idx_gvs=LOCS(iPeak)-time_gvs:LOCS(iPeak)+time_gvs;
    plot(rx(idx_tmp),ry(idx_tmp),'k.'); hold on
    plot(rx(idx_gvs),ry(idx_gvs),'r-','linewidth',2); hold on
    legend('Constant Current','GVS ON/OFF Switch');
    
    % covariance of x with y
%             n=100; % Number of points around ellipse
%             p=0:pi/n:2*pi; % angles around a circle
%             C = cov([rx(idx_tmp) ry(idx_tmp)]); % covariance of rx and ry
%             [eigvec,eigval] = eig(C) % Compute eigen-stuff
%             xy = [cos(p'),sin(p')] * sqrt(eigval) * eigvec'; % Transformation
%             x_ellips = xy(:,1) + mean(rx(idx_tmp));
%             y_ellips = xy(:,2) + mean(ry(idx_tmp));
%             plot(x_ellips,y_ellips,'ro')
%             axis equal
end






