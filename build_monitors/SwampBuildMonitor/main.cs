using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Security;
using Microsoft.Build.Framework;
using Microsoft.Build.Utilities;
using System.Xml;
using System.Text;
using System.Text.RegularExpressions;


namespace SwampBuildMonitor
{
    // This logger will derive from the Microsoft.Build.Utilities.Logger class,
    // which provides it with getters and setters for Verbosity and Parameters,
    // and a default empty Shutdown() implementation.
    public class XmlLogger : Logger
    {
	/// <summary>
	/// Initialize is guaranteed to be called by MSBuild at the start of the build
	/// before any events are raised.
	/// </summary>


	public override void Initialize(IEventSource eventSource)
	{
	    // The name of the log file should be passed as the first item in the
	    // "parameters" specification in the /logger switch.  It is required
	    // to pass a log file to this logger. Other loggers may have zero or more than 
	    // one parameters.
	    if (null == Parameters)
		{
		    throw new LoggerException("Log file was not set.");
		}
	    string[] parameters = Parameters.Split(';');
			
	    string logFile = parameters[0];
	    if (String.IsNullOrEmpty(logFile))
		{
		    throw new LoggerException("Log file was not set.");
		}
			
	    if (parameters.Length > 1)
		{
		    throw new LoggerException("Too many parameters passed.");
		}
			
	    try
		{
		    XmlWriterSettings settings = new XmlWriterSettings();
			settings.Encoding = Encoding.UTF8;
			// Open the file
		    this.xmlWriter = XmlWriter.Create(logFile, settings);
		}
	    catch (Exception ex)
		{
		    if
			(
			 ex is UnauthorizedAccessException
			 || ex is ArgumentNullException
			 || ex is PathTooLongException
			 || ex is DirectoryNotFoundException
			 || ex is NotSupportedException
			 || ex is ArgumentException
			 || ex is SecurityException
			 || ex is IOException
			 )
			{
			    throw new LoggerException("Failed to create log file: " + ex.Message);
			}
		    else
			{
			    // Unexpected failure
			    throw;
			}
		}

		this.xmlWriter.WriteStartDocument();
		this.xmlWriter.WriteStartElement("build-artifacts");
	    // For brevity, we'll only register for certain event types. Loggers can also
	    // register to handle TargetStarted/Finished and other events.
	    eventSource.ProjectStarted += new ProjectStartedEventHandler(eventSource_ProjectStarted);
	    eventSource.ProjectFinished += new ProjectFinishedEventHandler(eventSource_ProjectFinished);
		eventSource.TaskStarted += new TaskStartedEventHandler(eventSource_TaskStarted);
		eventSource.TaskFinished += new TaskFinishedEventHandler(eventSource_TaskFinished);
	    eventSource.MessageRaised += new BuildMessageEventHandler(eventSource_MessageRaised);
	    eventSource.WarningRaised += new BuildWarningEventHandler(eventSource_WarningRaised);
	    eventSource.ErrorRaised += new BuildErrorEventHandler(eventSource_ErrorRaised);
	}

	void eventSource_ErrorRaised(object sender, BuildErrorEventArgs e)
	{
	    // BuildErrorEventArgs adds LineNumber, ColumnNumber, File, amongst other parameters
	}
		
	void eventSource_WarningRaised(object sender, BuildWarningEventArgs e)
	{
	    // BuildWarningEventArgs adds LineNumber, ColumnNumber, File, amongst other parameters
	}

	void writeList(ArrayList array_list, String head_tag, String elem_tag) {
		if (array_list.Count == 0) {
			return;
		}
		this.xmlWriter.WriteStartElement(head_tag);
		foreach (String elem in array_list) {
			this.xmlWriter.WriteStartElement(elem_tag);
			this.xmlWriter.WriteCData(elem);
			this.xmlWriter.WriteEndElement();
		}			
		this.xmlWriter.WriteEndElement();
	}

	void eventSource_MessageRaised(object sender, BuildMessageEventArgs e)
	{
	    // BuildMessageEventArgs adds Importance to BuildEventArgs
	    // Let's take account of the verbosity setting we've been passed in deciding whether to log the message
	    if ((e.Importance == MessageImportance.High && IsVerbosityAtLeast(LoggerVerbosity.Minimal))
		|| (e.Importance == MessageImportance.Normal && IsVerbosityAtLeast(LoggerVerbosity.Normal))
		|| (e.Importance == MessageImportance.Low && IsVerbosityAtLeast(LoggerVerbosity.Detailed))				
		)
		{
			
				if (e.GetType().FullName == "Microsoft.Build.Framework.TaskCommandLineEventArgs") {
					this.xmlWriter.WriteStartElement("dotnet-compile");
					this.xmlWriter.WriteAttributeString("sender", e.SenderName);
					this.xmlWriter.WriteAttributeString("code", e.Code);
					this.xmlWriter.WriteAttributeString("sub-type", e.Subcategory);
					this.xmlWriter.WriteElementString("project-file", e.ProjectFile);

					this.xmlWriter.WriteStartElement("command-blob");
					this.xmlWriter.WriteCData(e.Message);
					this.xmlWriter.WriteEndElement();

					
					Regex regex = new Regex(@"(\x22[^\x22]+\x22|[^\s]+)");
					Regex msbuild_option = new Regex(@"/[\w]+:");

					//foreach (String match in args.) {
					ArrayList flags = new ArrayList();
					ArrayList classpath = new ArrayList();
					ArrayList srcfiles = new ArrayList();
					ArrayList analyzers = new ArrayList();

					bool seen_executable = false;
					foreach (String match in regex.Split(e.Message)) {
						 
						String arg = match;
						arg = arg.Trim();

						if (arg.Length == 0) {
							continue;
						}

						if (arg.StartsWith("\"") && arg.EndsWith("\"")) {
							arg = arg.Substring(1, arg.Length - 2); //removing quotes
						}

						if (seen_executable == false) {
							this.xmlWriter.WriteStartElement("executable");
							this.xmlWriter.WriteCData(arg);
							this.xmlWriter.WriteEndElement();
							seen_executable = true;
						}else if (arg.StartsWith("/reference:")) {
							classpath.Add(arg.Substring("/reference:".Length));
						} else if (arg.StartsWith("/analyzer:")) {
							analyzers.Add(arg.Substring("/analyzer:".Length));
						} else if (arg.StartsWith("/")) {
							if (arg.EndsWith(".cs")) {
								srcfiles.Add(arg);
							}else {
								flags.Add(arg);
							}
						} else {
							srcfiles.Add(arg);
						}
					}

					writeList(flags, "flags", "flag");
					writeList(classpath, "classpath", "file");
					writeList(analyzers, "analyzers", "file");
					writeList(srcfiles, "srcfile", "file");
					this.xmlWriter.WriteEndElement();
				}
		}
	}

	void eventSource_TaskStarted(object sender, TaskStartedEventArgs e)
	{
	    // TaskStartedEventArgs adds ProjectFile, TaskFile, TaskName
	}

	void eventSource_TaskFinished(object sender, TaskFinishedEventArgs e)
	{

	}
		
	void eventSource_ProjectStarted(object sender, ProjectStartedEventArgs e)
	{
		// ProjectStartedEventArgs adds ProjectFile, TargetNames
	}

	void eventSource_ProjectFinished(object sender, ProjectFinishedEventArgs e)
	{
		
	}
				
	/// <summary>
	/// Shutdown() is guaranteed to be called by MSBuild at the end of the build, after all 
	/// events have been raised.
	/// </summary>
	public override void Shutdown()
	{
	    // Done logging, let go of the file
		this.xmlWriter.WriteEndElement();
        this.xmlWriter.WriteEndDocument();
	    xmlWriter.Close();
	}

	private XmlWriter xmlWriter;

    }
}
