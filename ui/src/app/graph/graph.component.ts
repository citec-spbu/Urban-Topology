import { Component, OnInit, ViewChild, AfterViewInit, ElementRef, OnDestroy, Input, ChangeDetectorRef, Output, EventEmitter } from '@angular/core';
import { FileService } from '../services/file.service';
import { FormControl } from '@angular/forms';
import {density, diameter, simpleSize} from 'graphology-metrics/graph';
import Sigma from "sigma";
import Graph from 'graphology';
import iwanthue from "iwanthue";

import forceAtlas2 from 'graphology-layout-forceatlas2';

import circular from "graphology-layout/circular";
import {AbstractGraph} from 'graphology-types';
import saveAs from './saveAsPNG';
import { GraphData, GraphDataService } from '../services/graph-data.service';
import { debounceTime } from 'rxjs';

var graphml = require('graphology-graphml/browser');
var Graphology = require('graphology');

@Component({
  selector: 'app-graph',
  templateUrl: './graph.component.html',
  styleUrls: ['./graph.component.css']
})
export class GraphComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('sigmaContainer') container!: ElementRef;
  @Input() name?: string;

  @Input() graphData?: GraphData;
  @Input() loading: boolean = false;
  metrics?: {density: number, diameter: number, simpleSize: number};

  graph!: AbstractGraph;
  renderer?: Sigma;
  palette: string[] = [];
  labelsThreshold = new FormControl<number>(0);

  @Output() downloadLgraph = new EventEmitter();

  constructor(
    private cdRef: ChangeDetectorRef,
  ) {
  }

  ngOnInit(): void {
  }

  ngOnDestroy(): void {
    this.renderer?.kill();
    this.container?.nativeElement?.remove();
  }

  ngAfterViewInit(): void {
    // this.fileService.readFile('/assets/graphs/MurinoLO-4_graphml (1).graphml').subscribe(res => {
    //   // this.graph = graphml.parse(Graphology, res);
    //   this.setAttributes();
    //   this.render();
    //   this.getMetrics();
    // });
    this.graph = new Graph();
    if(!this.graphData) return;

    Object.values(this.graphData.nodes).forEach(node => {
      if(node) this.graph.addNode(node.way_id, {label: node.name, x: Number(node.lat), y: Number(node.lon), size: 5, way_id: node.way_id})
    });
    Object.values(this.graphData.edges).forEach(edge => this.graph.addEdge(edge.from, edge.to, {size: 5}));

    this.getMetrics();
    this.setAttributes();

    this.render();
  }

  getMetrics(){
    this.metrics = {
      density: density(this.graph),
      diameter: diameter(this.graph),
      simpleSize: simpleSize(this.graph)
    }
    this.cdRef.detectChanges();
  }

  setAttributes(){
    const nodes = this.graph.nodes();

    this.graph.forEachNode((node, attrs) => {
      // const size = Math.sqrt(this.graph.degree(node)) / 2;
      const size = this.graph.degree(node);
      attrs['size'] = size > 5 ? (size < 10 ? size : 10) : 5;
      attrs['color'] = iwanthue(1, {seed: attrs['way_id']})[0];
    });

    this.graph.forEachEdge((edge, attrs: any) => {
      attrs.size = 3;
    })
    
  }
  
  render(){
    if(!this.graph) return;
    circular.assign(this.graph);
    forceAtlas2.assign(this.graph, { settings: forceAtlas2.inferSettings(this.graph),  iterations: 600 });
    // let forceLayout = new ForceSupervisor(this.graph, {settings: });
    // let forceLayout = new FA2Layout(this.graph, {settings: forceAtlas2.inferSettings(this.graph)});
    // forceLayout.start();


    this.renderer = new Sigma(this.graph as any, this.container.nativeElement,  {renderEdgeLabels: true, renderLabels: true});
    
    this.labelsThreshold.valueChanges.pipe(debounceTime(50)).subscribe(val => {
      this.renderer?.setSetting("labelRenderedSizeThreshold", + (val ? val : 0));
    })

    const labelsThreshold = this.renderer.getSetting("labelRenderedSizeThreshold");
    if(labelsThreshold) this.labelsThreshold.setValue( labelsThreshold );
  }


  onSaveAs(type: 'png' | 'svg' | 'csv'){
    if(!this.renderer) return;

    if(type == 'csv') return this.downloadLgraph.emit();

    const layers = ["edges", "nodes", "labels"];  
    saveAs( type, this.renderer, layers);
  }
}
