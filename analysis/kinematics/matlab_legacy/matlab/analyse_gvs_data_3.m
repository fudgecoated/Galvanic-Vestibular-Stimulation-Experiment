%another complimentary program to compare COPx!!!

for i=1:max(n)%i=max(n)-2 %
    fileName=d(i).name;
    fileType=finfo(fileName);
    %if strcmp(fileType,'mat')
     if strcmp(fileName,'MA_PILOT_JAN2625_01.mat')

        [forcesAndMoments] = loadForcesFromHBCLBertecTreadmillMatFile(fileName,'forceFrequency',[sample_rate],'shouldFilter',[1],'filterCutoffFrequency',[30]);
        groundReactionMoments=forcesAndMoments.left.groundReactionMoments; % [Nm], measured at 1000 Hz, maybe ??
        groundReactionForces=forcesAndMoments.left.groundReactionForces; % [N], measured at 1000 Hz, maybe ??
        t=(0:length(groundReactionForces)-1)/sample_rate;
        idx_cut=t>90 | t<30; % indexing every sample after t=500 and before t=60
        t(idx_cut)=[];
        t=t-t(1); % to make sure time axis starts at 0
        groundReactionForces(idx_cut,:)=[]; % trow away everything after 525 seconds
        groundReactionMoments(idx_cut,:)=[]; % trow away everything after 525 seconds
        % cop position wrt back left side of treadmill. positive x-direction in the
        % walking direction. positive y-direction towards middle
        ry=groundReactionMoments(:,1)./groundReactionForces(:,3); % [m]
        rx=-groundReactionMoments(:,2)./groundReactionForces(:,3); % [m]
        
        % COP velocity profile (looking at this to find start of GVS
        ryd=diff(ry)*sample_rate; % [m/s] velocity of cop in y direction. delta y / delta time (1/sf)
        rxd=diff(rx)*sample_rate;
        v_r=sqrt(ryd.^2+rxd.^2); %computes the magnitude of the velocity coordinates (pythagoras)
        
        find peaks in v_cop
        figure;
        [~,LOCS] = findpeaks(v_r,'MinPeakDistance',58*sample_rate,'MinPeakHeight',0.1, 'NPeaks',6);
        findpeaks(v_r,sample_rate,'MinPeakDistance',58,'MinPeakHeight',0.1,'NPeaks',6)
        xticks([0 30 60 90])
        xlabel('Time (s)')
        ylabel('COP velocity (m/s)')
        
%         %add a corresponding plot with the COPx above the findpeaks output
        figure;plot(t,rx,'k')
        xticks([0 30 60])
        title('COP x-Coordinate and Magnitude of Velocity as a Function of Time')
        xlabel('Time (s)')
        ylabel('COPx (m)')
        axis([0 60 -0.245 -0.28]);
        %export_fig shaine_cop_x_velocity -transparent -TIFF
        

        
        make pretty pictures
        animation!! Cool stuff!!
                for iPeak=1:length(LOCS) % we are gonna do something for every peak
                    figure
                    %axis equal; hold on
                    axis([-0.40 -0.2 0.35 0.55]); hold on %this will ensure axis are in similar proportions. NEED TO ALTER THE LIMITS BASED ON TRIAL
                    xlabel('left-right sway [m]')
                    ylabel('front-back sway [m]')
                    time_span=20*sample_rate; % nr of samples to look at round peak
                    idx_tmp=LOCS(iPeak)-time_span:LOCS(iPeak)+time_span;
                    comet(rx(idx_tmp),ry(idx_tmp),0.2);
                    %comet3(rx(idx_tmp),ry(idx_tmp),t(idx_tmp)); %add temporality
        
        
                end
        
        
        CUSTOM LOCATION SETTING
        LOCScustom = [90000;147600;205200;262800;320400;350000]; %total time (from beginning of forceplate measurement) x sample rate; (60s x 960 = 57600); first one = X seconds + 1min increments
        look at groundReactionForces/Moments for the number of total
        samples; ensure that the final value you pic is consistent with
        the time_span function for the animations. (eg.
        time_span=20*sample_rate and thus 20*960 = 19600. THEREFORE, the
        top value must be 19600 below the total samples or else it cannot
        be indexed
        
        
                %ANIMATIONS AT CUSTOM LOCATIONS
                for iPeak=1:length(LOCScustom) % we are gonna do something for every peak
                    figure
                    %axis equal; hold on
                    axis([-0.40 -0.2 0.35 0.55]); hold on %this will ensure axis are in similar proportions. NEED TO ALTER THE LIMITS BASED ON TRIAL
                    xlabel('left-right sway [m]')
                    ylabel('front-back sway [m]')
                    time_span=20*sample_rate; % nr of samples to look at round peak
                    idx_tmp=LOCScustom(iPeak)-time_span:LOCScustom(iPeak)+time_span;
                    comet(rx(idx_tmp),ry(idx_tmp),0.2);
                    %comet3(rx(idx_tmp),ry(idx_tmp),t(idx_tmp)); %add temporality
                end
        
        
        %make general COP plots for each software detected peak
        for iPeak=1:length(LOCS) % we are gonna do something for every peak
            figure
            axis equal; hold on %this will ensure axis are in similar proportions. NEED TO ALTER THE LIMITS BASED ON TRIAL
            xlabel('Left-Right Sway (m)')
            ylabel('Front-Back sway (m)')
            title('x- and y-Coordinate COP Profile During Constant Current GVS')
            time_span=10*sample_rate; % nr of samples to look at round peak
            time_gvs=3*sample_rate;
            idx_tmp=LOCS(iPeak)-time_span:LOCS(iPeak)+time_span;
            idx_gvs=LOCS(iPeak)-time_gvs:LOCS(iPeak)+time_gvs;
            plot(rx(idx_tmp),ry(idx_tmp),'k.'); hold on
            plot(rx(idx_gvs),ry(idx_gvs),'r-','linewidth',2); hold on
            legend('Constant Current','GVS ON/OFF Switch');
            
            covariance of x with y
            n=100; % Number of points around ellipse
            p=0:pi/n:2*pi; % angles around a circle
            C = cov([rx(idx_tmp) ry(idx_tmp)]); % covariance of rx and ry
            [eigvec,eigval] = eig(C) % Compute eigen-stuff
            xy = [cos(p'),sin(p')] * sqrt(eigval) * eigvec'; % Transformation
            x_ellips = xy(:,1) + mean(rx(idx_tmp));
            y_ellips = xy(:,2) + mean(ry(idx_tmp));
            plot(x_ellips,y_ellips,'ro')
            axis equal
        end
        
        
        make general COP plots @ CUSTOM LOCATIONS as indicated by the
        CUSTOM LOCATIONS SETTINGS
                 for iPeak=1:length(LOCScustom) % we are gonna do something for every peak
                     figure
                     axis([-0.36 -0.21 0.40 0.55]); hold on %this will ensure axis are in similar proportions. NEED TO ALTER THE LIMITS BASED ON TRIAL
                     xlabel('left-right sway [m]')
                     ylabel('front-back sway [m]')
                     time_span=20*sample_rate; % nr of samples to look at round peak
                     idx_tmp=LOCScustom(iPeak)-time_span:LOCScustom(iPeak)+time_span;
                     plot(rx(idx_tmp),ry(idx_tmp));
                 end
        
        
        we are plotting the forces over time for all coordinates
                figure;subplot(211);plot(t,groundReactionForces(:,3))
                ylim ([810 870]) %this is set holistically based on subject body mass. look at groundReactionForces 3rd column (:,3) for estimated z-Force
                xticks([0 60 120 180 240 300 360 420 480 540]) %better to see in terms of minutes
                title('z axis')
                xlabel('Time [s]')
                ylabel('Force [N]')
        
                subplot(212);plot(t,groundReactionForces(:,1:2))
                ylim ([-65 15]) %holistically set
                xticks([0 60 120 180 240 300 360 420 480 540])
                title('x and y axis')
                xlabel('Time [s]')
                ylabel('Force [N]')
        
        
        COPx and y over time to see effect
        figure;plot(t,rx)
        xticks([0 60 120 180 240 300 360 420 480 540])
        title('x coordinate over time')
        xlabel('time [s]')
        ylabel('COPx [m]')
        
        figure;plot(t,ry)
        xticks([0 60 120 180 240 300 360 420 480 540])
        title('y coordinate over time')
        xlabel('Time (s)')
        ylabel('COPy (m)')
        
        figure;plot(t(2:end),rxd)
        xticks([0 60 120 180 240 300 360 420 480 540])
        title('x coordinate over time')
        xlabel('time [s]')
        ylabel('COPx [m]')
        
        
                for iPeak=1:length(LOCS) % we are gonna do something for every peak
                    figure
                    time_span=2*sample_rate; % nr of samples to look at round peak
                    idx_tmp=LOCS(iPeak)-time_span:LOCS(iPeak)+time_span;
                    plot(rx(idx_tmp),ry(idx_tmp),'.'); hold on
                    delay_tmp=LOCS(iPeak)-0.5*sample_rate;
                    %plot(rx(delay_tmp),ry(delay_tmp),'ro'); %hold on
                    plot([rx(delay_tmp) rx(delay_tmp)+rxd(delay_tmp)],[ry(delay_tmp) ry(delay_tmp)+ryd(delay_tmp)],'r'); %hold on
                    xlabel('fore-aft [m]')
                    ylabel('left-right [m]')
                    axis equal
                end
                %xlim([mean(rx)-.5*range mean(rx)+.5*range])
        ylim([mean(ry)-.5*range mean(ry)+.5*range])
        
    end
end

